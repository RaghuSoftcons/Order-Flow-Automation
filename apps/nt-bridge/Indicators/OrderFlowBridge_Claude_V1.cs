// ============================================================================
// OrderFlowBridge_Claude_V1
// ============================================================================
// File:        OrderFlowBridge_Claude_V1.cs
// Created:     2026-04-26 19:10 EST
// Author:      Claude (Anthropic) + Raghu
// Version:     1.0.0
// Last Modified: 2026-04-26 19:10 EST
//
// PURPOSE
//   Streams Level 2 depth + trade events from NinjaTrader 8 to the Order Flow
//   Automation Railway service via WebSocket. One indicator instance per chart
//   per symbol — add to ES, NQ, GC charts (any timeframe).
//
// CHANGE LOG
//   2026-04-26 19:10 EST | 1.0.0 | Phase 1D initial: WebSocket bridge with
//     throttled depth snapshots, immediate trade events, config from JSON,
//     auto-reconnect, ConcurrentQueue outbox.
//   2026-04-26 20:00 EST | 1.0.1 | Fix CS0305 compile error: NT8 does not
//     expose a `MarketDepth` accessor on Indicator. Maintain local DOM
//     (SortedDictionary per side) by accumulating OnMarketDepth events.
//
// CONFIGURATION
//   Reads JSON from:
//     %USERPROFILE%\Documents\NinjaTrader 8\OrderFlowBridge\config.json
//   Schema:
//     {
//       "server_url": "wss://order-flow-automation-production.up.railway.app/ws/nt-ingest",
//       "api_key": "ofa_xxx",
//       "snapshot_interval_ms": 250,
//       "max_levels": 10,
//       "log_verbose": false
//     }
//
// PROP-FIRM SAFETY
//   Phase 1D is data-egress ONLY. No order placement, no account access,
//   no PnL state. Read-only on the NT side; the only outbound calls are
//   JSON depth/trade events to a single configured WebSocket URL.
// ============================================================================

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Linq;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using Newtonsoft.Json;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class OrderFlowBridge_Claude_V1 : Indicator
    {
        // ---------- Config (loaded from JSON) ----------
        private class BridgeConfig
        {
            [JsonProperty("server_url")] public string ServerUrl { get; set; } = "";
            [JsonProperty("api_key")]    public string ApiKey    { get; set; } = "";
            [JsonProperty("snapshot_interval_ms")] public int SnapshotIntervalMs { get; set; } = 250;
            [JsonProperty("max_levels")] public int MaxLevels    { get; set; } = 10;
            [JsonProperty("log_verbose")] public bool LogVerbose { get; set; } = false;
        }

        private BridgeConfig _config;
        private string _configPath;

        // ---------- WebSocket plumbing ----------
        private ClientWebSocket _ws;
        private CancellationTokenSource _cts;
        private Task _senderTask;
        private readonly ConcurrentQueue<string> _outbox = new ConcurrentQueue<string>();
        private readonly ManualResetEventSlim _outboxSignal = new ManualResetEventSlim(false);
        private System.Threading.Timer _snapshotTimer;

        private int _depthDirty;       // Interlocked flag (0/1)
        private long _lastSnapshotTicks;
        private long _eventsSent;
        private long _eventsFailed;

        // ---------- Symbol metadata ----------
        private string _symbolRoot;    // "ES"
        private string _contractName;  // "ES 06-26"

        // ---------- Local DOM (maintained from OnMarketDepth events) ----------
        // SortedDictionary keyed by price. Bid and ask are separate.
        // We read these from a single thread (the snapshot timer), so a simple
        // lock is enough. Two dicts keep insert/update/remove O(log N).
        private readonly SortedDictionary<double, long> _localBids = new SortedDictionary<double, long>();
        private readonly SortedDictionary<double, long> _localAsks = new SortedDictionary<double, long>();
        private readonly object _domLock = new object();

        protected override void OnStateChange()
        {
            try
            {
                if (State == State.SetDefaults)
                {
                    Description = @"Streams L2 depth + trades to Order Flow Automation backend via WebSocket.";
                    Name = "OrderFlowBridge_Claude_V1";
                    Calculate = Calculate.OnEachTick;
                    IsOverlay = true;
                    DisplayInDataBox = false;
                    DrawOnPricePanel = false;
                    PaintPriceMarkers = false;
                    IsSuspendedWhileInactive = false;
                }
                else if (State == State.Configure)
                {
                    LoadConfig();
                }
                else if (State == State.DataLoaded)
                {
                    if (_config == null) return;
                    _symbolRoot   = Instrument?.MasterInstrument?.Name ?? "UNKNOWN";
                    _contractName = Instrument?.FullName ?? _symbolRoot;
                    Log("starting bridge for " + _contractName + " (root=" + _symbolRoot + ")");
                    StartBackgroundLoop();
                }
                else if (State == State.Terminated)
                {
                    Log("terminating bridge for " + _contractName);
                    Shutdown();
                }
            }
            catch (Exception ex)
            {
                Print("[OrderFlowBridge] OnStateChange exception: " + ex.Message);
            }
        }

        protected override void OnBarUpdate()
        {
            // No bar logic; events fire via OnMarketData / OnMarketDepth.
        }

        // ---------- Live event hooks ----------

        protected override void OnMarketData(MarketDataEventArgs e)
        {
            if (_config == null || e.MarketDataType != MarketDataType.Last) return;
            try
            {
                string aggressor;
                // NT exposes Bid/Ask alongside the trade; aggressor inferred from price vs touch.
                if (e.Price >= e.Ask) aggressor = "buy";
                else if (e.Price <= e.Bid) aggressor = "sell";
                else aggressor = e.Price >= (e.Bid + e.Ask) / 2.0 ? "buy" : "sell";

                var json = JsonConvert.SerializeObject(new
                {
                    type = "trade",
                    symbol = _symbolRoot,
                    contract = _contractName,
                    ts_utc = DateTime.UtcNow.ToString("o"),
                    price = e.Price,
                    size = (int)e.Volume,
                    aggressor
                });
                Enqueue(json);
            }
            catch (Exception ex)
            {
                Print("[OrderFlowBridge] OnMarketData exception: " + ex.Message);
            }
        }

        protected override void OnMarketDepth(MarketDepthEventArgs e)
        {
            // NT fires per-level deltas. We accumulate into _localBids/_localAsks
            // and let the snapshot timer flush the current top N at most once per
            // snapshot_interval_ms (NT can fire hundreds of these per second).
            try
            {
                var dom = e.MarketDataType == MarketDataType.Bid ? _localBids : _localAsks;
                lock (_domLock)
                {
                    switch (e.Operation)
                    {
                        case Operation.Insert:
                        case Operation.Update:
                            if (e.Volume > 0) dom[e.Price] = (long)e.Volume;
                            else dom.Remove(e.Price);
                            break;
                        case Operation.Remove:
                            dom.Remove(e.Price);
                            break;
                    }
                }
                Interlocked.Exchange(ref _depthDirty, 1);
            }
            catch (Exception ex)
            {
                Print("[OrderFlowBridge] OnMarketDepth exception: " + ex.Message);
            }
        }

        // ---------- Snapshot timer ----------

        private void SnapshotTick(object state)
        {
            try
            {
                if (Interlocked.Exchange(ref _depthDirty, 0) == 0) return;

                List<object> bids;
                List<object> asks;
                int maxLevels = _config.MaxLevels;

                lock (_domLock)
                {
                    // Bids descending (highest price first); take top N
                    bids = _localBids
                        .Reverse()
                        .Take(maxLevels)
                        .Select(kv => (object)new { price = kv.Key, size = (int)kv.Value, orders = 0 })
                        .ToList();
                    // Asks ascending (lowest price first); take top N
                    asks = _localAsks
                        .Take(maxLevels)
                        .Select(kv => (object)new { price = kv.Key, size = (int)kv.Value, orders = 0 })
                        .ToList();
                }

                if (bids.Count == 0 && asks.Count == 0) return;

                var json = JsonConvert.SerializeObject(new
                {
                    type = "depth",
                    symbol = _symbolRoot,
                    contract = _contractName,
                    ts_utc = DateTime.UtcNow.ToString("o"),
                    bids,
                    asks
                });
                Enqueue(json);
                _lastSnapshotTicks = DateTime.UtcNow.Ticks;
            }
            catch (Exception ex)
            {
                Print("[OrderFlowBridge] SnapshotTick exception: " + ex.Message);
            }
        }

        // ---------- Outbox + sender loop ----------

        private void Enqueue(string json)
        {
            _outbox.Enqueue(json);
            _outboxSignal.Set();
        }

        private void StartBackgroundLoop()
        {
            _cts = new CancellationTokenSource();
            _senderTask = Task.Run(() => SenderLoopAsync(_cts.Token));
            int interval = Math.Max(50, _config.SnapshotIntervalMs);
            _snapshotTimer = new System.Threading.Timer(SnapshotTick, null, interval, interval);
        }

        private async Task SenderLoopAsync(CancellationToken ct)
        {
            int backoffMs = 500;
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    if (_ws == null || _ws.State != WebSocketState.Open)
                    {
                        await ConnectAsync(ct);
                        backoffMs = 500;
                    }

                    _outboxSignal.Wait(500, ct);
                    _outboxSignal.Reset();

                    string msg;
                    while (_outbox.TryDequeue(out msg))
                    {
                        var bytes = Encoding.UTF8.GetBytes(msg);
                        try
                        {
                            await _ws.SendAsync(new ArraySegment<byte>(bytes),
                                                WebSocketMessageType.Text, true, ct);
                            Interlocked.Increment(ref _eventsSent);
                        }
                        catch (Exception sendEx)
                        {
                            Interlocked.Increment(ref _eventsFailed);
                            // requeue so we don't lose the event over a transient disconnect
                            _outbox.Enqueue(msg);
                            Log("send failed (" + sendEx.Message + "); will reconnect");
                            await SafeCloseAsync();
                            break;
                        }
                    }
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Log("sender loop exception: " + ex.Message);
                    await SafeCloseAsync();
                    try { await Task.Delay(backoffMs, ct); } catch { break; }
                    backoffMs = Math.Min(backoffMs * 2, 15000);
                }
            }
        }

        private async Task ConnectAsync(CancellationToken ct)
        {
            await SafeCloseAsync();
            _ws = new ClientWebSocket();
            string sep = _config.ServerUrl.Contains("?") ? "&" : "?";
            string url = _config.ServerUrl + sep + "api_key=" + Uri.EscapeDataString(_config.ApiKey);
            Log("connecting to " + _config.ServerUrl);
            await _ws.ConnectAsync(new Uri(url), ct);
            Log("connected; sent=" + _eventsSent + " failed=" + _eventsFailed);
        }

        private async Task SafeCloseAsync()
        {
            if (_ws == null) return;
            try
            {
                if (_ws.State == WebSocketState.Open)
                    await _ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "shutdown", CancellationToken.None);
            }
            catch { /* ignore */ }
            finally
            {
                _ws.Dispose();
                _ws = null;
            }
        }

        // ---------- Lifecycle ----------

        private void Shutdown()
        {
            try
            {
                _snapshotTimer?.Dispose();
                _snapshotTimer = null;
                _cts?.Cancel();
                _outboxSignal.Set();
                _senderTask?.Wait(2000);
                SafeCloseAsync().Wait(2000);
            }
            catch (Exception ex)
            {
                Print("[OrderFlowBridge] shutdown exception: " + ex.Message);
            }
        }

        private void LoadConfig()
        {
            try
            {
                _configPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "OrderFlowBridge", "config.json");
                if (!File.Exists(_configPath))
                {
                    Print("[OrderFlowBridge] config not found at " + _configPath +
                          " — bridge will not start. See nt_bridge_setup.md");
                    _config = null;
                    return;
                }
                var text = File.ReadAllText(_configPath);
                _config = JsonConvert.DeserializeObject<BridgeConfig>(text);
                if (_config == null || string.IsNullOrEmpty(_config.ServerUrl) || string.IsNullOrEmpty(_config.ApiKey))
                {
                    Print("[OrderFlowBridge] config is missing server_url or api_key");
                    _config = null;
                }
            }
            catch (Exception ex)
            {
                Print("[OrderFlowBridge] LoadConfig exception: " + ex.Message);
                _config = null;
            }
        }

        private void Log(string msg)
        {
            if (_config != null && _config.LogVerbose) Print("[OrderFlowBridge] " + msg);
            else if (msg.StartsWith("starting") || msg.StartsWith("terminating") ||
                     msg.StartsWith("connecting") || msg.StartsWith("connected") ||
                     msg.StartsWith("send failed") || msg.StartsWith("sender loop"))
                Print("[OrderFlowBridge] " + msg);
        }
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private OrderFlowBridge_Claude_V1[] cacheOrderFlowBridge_Claude_V1;
        public OrderFlowBridge_Claude_V1 OrderFlowBridge_Claude_V1()
        {
            return OrderFlowBridge_Claude_V1(Input);
        }

        public OrderFlowBridge_Claude_V1 OrderFlowBridge_Claude_V1(ISeries<double> input)
        {
            if (cacheOrderFlowBridge_Claude_V1 != null)
                for (int idx = 0; idx < cacheOrderFlowBridge_Claude_V1.Length; idx++)
                    if (cacheOrderFlowBridge_Claude_V1[idx] != null && cacheOrderFlowBridge_Claude_V1[idx].EqualsInput(input))
                        return cacheOrderFlowBridge_Claude_V1[idx];
            return CacheIndicator<OrderFlowBridge_Claude_V1>(new OrderFlowBridge_Claude_V1(), input, ref cacheOrderFlowBridge_Claude_V1);
        }
    }
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
    public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
    {
        public Indicators.OrderFlowBridge_Claude_V1 OrderFlowBridge_Claude_V1()
        {
            return indicator.OrderFlowBridge_Claude_V1(Input);
        }

        public Indicators.OrderFlowBridge_Claude_V1 OrderFlowBridge_Claude_V1(ISeries<double> input )
        {
            return indicator.OrderFlowBridge_Claude_V1(input);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.OrderFlowBridge_Claude_V1 OrderFlowBridge_Claude_V1()
        {
            return indicator.OrderFlowBridge_Claude_V1(Input);
        }

        public Indicators.OrderFlowBridge_Claude_V1 OrderFlowBridge_Claude_V1(ISeries<double> input )
        {
            return indicator.OrderFlowBridge_Claude_V1(input);
        }
    }
}

#endregion
