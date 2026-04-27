<!--
File:        docs/nt_bridge_setup.md
Created:     2026-04-26 19:15 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 19:15 EST
-->

# NinjaTrader Bridge Setup (Phase 1D)

`OrderFlowBridge_Claude_V1` is a NinjaScript **Indicator** that streams Level 2 depth and trades from NT8 to the Railway service via WebSocket.

It is data-egress only. No orders are placed by this version. Order placement comes in Phase 3.

## One-time setup

### 1. Copy the indicator file into NT's custom folder

The canonical source lives in this repo at:
```
apps/nt-bridge/Indicators/OrderFlowBridge_Claude_V1.cs
```

Copy it to:
```
C:\Users\owner\Documents\NinjaTrader 8\bin\Custom\Indicators\Raghu\OrderFlowBridge_Claude_V1.cs
```

### 2. Compile in NT

1. Open NinjaTrader 8.
2. Menu: **Tools → Edit NinjaScript → Indicator** → it auto-compiles.
3. Alternatively: **Tools → Compile NinjaScript** (F5 in the editor).
4. Watch the **Output window** (Tools → Output Window) for compile errors.

### 3. Create the config file

Path:
```
C:\Users\owner\Documents\NinjaTrader 8\OrderFlowBridge\config.json
```

Contents (replace the placeholder values):

```json
{
  "server_url": "wss://order-flow-automation-production.up.railway.app/ws/nt-ingest",
  "api_key": "ofa_PASTE_YOUR_ADMIN_API_KEY_HERE",
  "snapshot_interval_ms": 250,
  "max_levels": 10,
  "log_verbose": false
}
```

Notes:
- `api_key` must be an **admin** key (the one printed for `raghu@softcons.net` by `seed-users`)
- `snapshot_interval_ms` controls how often a depth snapshot is sent. 250 ms is a good default. Lower = more bandwidth + more events; higher = staler book
- `log_verbose: true` writes a line to the NT Output window for every connect/disconnect/send error. Useful for debugging; turn off in steady state

### 4. Add the indicator to a chart

For each symbol you want bridged (ES, NQ, GC):

1. Open a chart for that contract (e.g. `ES 06-26`, any timeframe — the indicator doesn't read bars)
2. Right-click the chart → **Indicators…**
3. Find **OrderFlowBridge_Claude_V1** in the list (under Indicators)
4. Add it. No parameters to configure (everything comes from the JSON config)
5. Click **OK**

You should see in the **Output window** (Tools → Output Window):
```
[OrderFlowBridge] starting bridge for ES 06-26 (root=ES)
[OrderFlowBridge] connecting to wss://order-flow-automation-production.up.railway.app/ws/nt-ingest
[OrderFlowBridge] connected; sent=0 failed=0
```

### 5. Verify on Railway

```bash
# Replace with your admin key
curl -H "X-API-Key: <key>" \
  https://order-flow-automation-production.up.railway.app/orderbook?symbol=ES | jq

curl -H "X-API-Key: <key>" \
  https://order-flow-automation-production.up.railway.app/health/feed | jq
```

`/orderbook` should return populated `bids` and `asks`. `/health/feed` should show ES status as `fresh`.

## Usual gotchas

| Symptom | Likely cause | Fix |
|---|---|---|
| "config not found at..." in Output window | `config.json` not at the expected path | Create the folder + file exactly as in step 3 |
| Bridge logs "connecting" then nothing | Railway service is asleep / restarting | Wait ~30s; if persistent, check Railway logs |
| Auth errors / 401 in NT log | Wrong api_key or non-admin user | Verify the key matches an admin user in the Railway DB |
| Lots of "send failed" lines | Network flapping or Railway redeploying | Self-heals via auto-reconnect; check NT Output for the actual error |
| Compile error: `using System.Net.WebSockets` not found | Older NT8 or trimmed runtime | Update NT8 to 8.1+; this namespace is in .NET Framework 4.5+ |
| Bridge runs but `/orderbook` is empty | Indicator added to a chart with no Level 2 data subscription | Right-click chart → Properties → confirm "Show Market Depth" or your data feed includes L2 |

## Updating the bridge

When this file is modified in the repo, copy the new `.cs` file over the existing one in the NT folder, then **Tools → Compile NinjaScript** (F5). Charts running the old version pick up the new one on their next state transition (or close + re-add the indicator).

Per the global convention (CLAUDE.md): both the repo file at `apps/nt-bridge/Indicators/` AND the NT8 path get updated together.

## What this bridge intentionally does NOT do

- Place, modify, or cancel orders (Phase 3)
- Read account balances or PnL (not needed for data egress)
- Persist state to disk (memory-only; restart loses any in-flight events)
- Subscribe to multiple symbols from one indicator instance (use one chart per symbol)

## Where to next

When the bridge is reliably streaming for a session or two, you're ready for **Phase 2**: adding the Claude tool layer that reads `/orderbook` and `/liquidity-snapshot` and produces trade verdicts.
