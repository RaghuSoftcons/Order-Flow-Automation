<!--
File:        docs/replay.md
Created:     2026-04-26 18:56 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:56 EST
-->

# Replay Harness (Phase 1C)

Pump synthetic or historical events into the order book engine without waiting for live market hours.

## Two sources

| Source | When to use | Cost |
|---|---|---|
| **Synthetic** | Dev, demo, regression tests | $0, no signup |
| **Databento DBN** | Realistic CME tape for Phase 2 AI validation | $125 free credits per Databento account |

## Two sinks

| Sink | When to use |
|---|---|
| **HTTP** (`POST /ingest/event` per event) | Local dev, low rate (<10 events/sec), tests |
| **WebSocket** (`/ws/nt-ingest` persistent) | Production replay against live Railway |

## Quick start — synthetic to local

```bash
# Terminal 1: start API
source .venv/Scripts/activate
python -m orderflow_api.cli seed-users   # save the printed admin key
PYTHONPATH=apps/api/src:packages/shared/src \
  uvicorn orderflow_api.main:app --reload --port 8000

# Terminal 2: push 60s of synthetic ES events
source .venv/Scripts/activate
PYTHONPATH=apps/api/src:packages/shared/src \
  python -m orderflow_shared.replay.cli synthetic \
    --symbol ES --duration 60 \
    --target http://localhost:8000 \
    --api-key ofa_xxx --sink http

# Terminal 3: read it back
curl -H "X-API-Key: ofa_xxx" http://localhost:8000/orderbook?symbol=ES | jq
curl -H "X-API-Key: ofa_xxx" http://localhost:8000/liquidity-snapshot?symbol=ES | jq
```

## Quick start — synthetic to Railway via WebSocket

```bash
PYTHONPATH=apps/api/src:packages/shared/src \
  python -m orderflow_shared.replay.cli synthetic \
    --symbol NQ --duration 300 --depth-rate 5 --trade-rate 3 \
    --target wss://order-flow-automation-production.up.railway.app/ws/nt-ingest \
    --api-key ofa_xxx --sink ws
```

Add `--pace-realtime` to make events fire at their original cadence (useful when validating Phase 2 AI behavior under realistic timing). Without it, events fire as fast as the network allows.

## Databento (real CME tape)

1. Sign up at https://databento.com — get $125 free credits.
2. Buy a slice of MBP-10 history for `GLBX.MDP3` (e.g., one trading day of front-month ES). The Databento UI walks you through the order; output is a `.dbn` file.
3. Install the SDK in your venv:
   ```bash
   pip install databento
   ```
4. Replay it:
   ```bash
   PYTHONPATH=apps/api/src:packages/shared/src \
     python -m orderflow_shared.replay.cli databento \
       --file ~/Downloads/glbx-mdp3-20260420.mbp-10.dbn \
       --target wss://order-flow-automation-production.up.railway.app/ws/nt-ingest \
       --api-key ofa_xxx --sink ws --pace-realtime
   ```

## Determinism (synthetic only)

Same `--seed` produces a byte-identical event stream. Useful for regression tests:

```bash
python -m orderflow_shared.replay.cli synthetic --duration 30 --seed 123 ...
```

## Known limits

- **Synthetic source is not a market simulator.** Prices walk randomly; depth shapes are heuristic. Good enough for engine + AI plumbing, not for strategy backtests.
- **HTTPSink is one POST per event.** ~50–100 events/sec is the practical ceiling. Use WebSocketSink above that.
- **WebSocket replay state lives in the Railway container's RAM.** A redeploy clears it. Phase 3 moves state to Redis to fix this.
- **Databento adapter today only handles MBP-10.** MBO records will need a separate path.
