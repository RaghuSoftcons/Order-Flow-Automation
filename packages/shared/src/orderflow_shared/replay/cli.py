"""
File:        packages/shared/src/orderflow_shared/replay/cli.py
Created:     2026-04-26 18:53 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:53 EST

Change Log:
- 2026-04-26 18:53 EST | 1.0.0 | Phase 1C: replay CLI.

Examples:
    # Push 60s of synthetic ES data to a local server via HTTP
    python -m orderflow_shared.replay.cli synthetic --symbol ES --duration 60 \\
        --target http://localhost:8000 --api-key $KEY --sink http

    # Push synthetic data to live Railway via WebSocket
    python -m orderflow_shared.replay.cli synthetic --symbol NQ --duration 120 \\
        --target wss://order-flow-automation-production.up.railway.app/ws/nt-ingest \\
        --api-key $KEY --sink ws

    # Replay a Databento DBN file
    python -m orderflow_shared.replay.cli databento --file es_20260420.dbn \\
        --target wss://.../ws/nt-ingest --api-key $KEY --sink ws
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Sequence

from orderflow_shared.replay.sink import HTTPSink, WebSocketSink
from orderflow_shared.replay.synthetic import SyntheticConfig, SyntheticSource


def _build_synth_source(args: argparse.Namespace) -> SyntheticSource:
    cfg = SyntheticConfig(
        symbol=args.symbol,
        start_price=args.start_price,
        duration_seconds=args.duration,
        depth_event_rate_hz=args.depth_rate,
        trade_event_rate_hz=args.trade_rate,
        seed=args.seed,
    )
    return SyntheticSource(config=cfg)


def _build_databento_source(args: argparse.Namespace):  # noqa: ANN202
    from orderflow_shared.replay.databento_source import DatabentoMBP10Source

    return DatabentoMBP10Source(file_path=args.file)


def _run_http(source, target: str, api_key: str) -> int:
    sink = HTTPSink(base_url=target, api_key=api_key)
    try:
        for event in source:
            sink.push(event)
    finally:
        sink.close()
    print(f"sent={sink.sent} failed={sink.failed} last_error={sink._last_error}")
    return 0 if sink.failed == 0 else 1


def _run_ws(source, target: str, api_key: str, pace_realtime: bool) -> int:
    sink = WebSocketSink(url=target, api_key=api_key)
    result = asyncio.run(sink.run(list(source), pace_realtime=pace_realtime))
    print(f"sent={result['sent']} failed={result['failed']} last_error={result['last_error']}")
    return 0 if result["failed"] == 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orderflow-replay")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--target", required=True, help="Base URL (http) or WS URL")
    common.add_argument("--api-key", required=True, help="Admin API key")
    common.add_argument("--sink", choices=["http", "ws"], default="http")
    common.add_argument("--pace-realtime", action="store_true",
                        help="WS only: sleep so events fire at original cadence")

    synth = sub.add_parser("synthetic", parents=[common])
    synth.add_argument("--symbol", default="ES")
    synth.add_argument("--start-price", type=float, default=5285.00)
    synth.add_argument("--duration", type=float, default=60.0)
    synth.add_argument("--depth-rate", type=float, default=4.0)
    synth.add_argument("--trade-rate", type=float, default=2.0)
    synth.add_argument("--seed", type=int, default=42)

    db = sub.add_parser("databento", parents=[common])
    db.add_argument("--file", required=True, help="Path to DBN file (mbp-10 schema)")

    args = parser.parse_args(argv)

    if args.cmd == "synthetic":
        source = _build_synth_source(args)
    elif args.cmd == "databento":
        source = _build_databento_source(args)
    else:
        parser.print_help()
        return 1

    if args.sink == "http":
        return _run_http(source, args.target, args.api_key)
    return _run_ws(source, args.target, args.api_key, args.pace_realtime)


if __name__ == "__main__":
    sys.exit(main())
