"""RQ3 confirmatory battery — operator-gated LIVE launcher (triple-locked).

The RQ3 family (RQ3-P1-perf, RQ3-P1-latency, RQ3-P2) is part of the **frozen LEAD
prereg** (`sor-consent-prereg.md` §3/§6, family-of-7); the companion run-brief
(`docs/rq3-companion-run-brief.md`) pins the churn params (kp=30, steps=20) and the
selector arms. This launcher is the RQ3 analogue of ``confirmatory_run.py``: it
collects the confirmatory battery ONLY behind the same triple-lock the lead battery
uses, because the RQ3-P1-latency DV is a **real end-to-end measurement** on isolated
docker circuits — nothing here is fabricated.

Triple-lock (all three or refuse):
  1. **Operator token** — ``SOR_CONFIRMATORY_GO=1`` in the environment.
  2. **Frozen-prereg SHA-256** — the on-disk lead prereg still hashes to the pinned
     value (``confirmatory_run.verify_freeze``); no run against an unfrozen/edited prereg.
  3. **Isolation** — ``assert_isolated(engine)`` (``engine != local``); every hop runs
     in an isolated docker container, never on the host (CLAUDE.md §Containment).

Green-preflight preconditions (checked, not fabricated): the two RQ3 calibration
gates (churn-bites + rebuild-classifier) already pass; the grid is up with >=1
isolated engine host; the ``sor-hop`` image is present; a 1x1x2 live rehearsal
delivered. Then ``executor.run_rq3_battery(live=True)`` runs the full frozen
schedule (selector ∈ {static, random, agent} × pinned churn, R runs × C circuits) —
cells are NOT trimmed. Progress: per-run ``rq3-run.json`` sidecars appear under the
data dir; completion: ``rq3-battery-results.json`` is written once at the end.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cmd_chat.sor import battery
from cmd_chat.sor.confirmatory_run import OPERATOR_TOKEN_ENV, verify_freeze
from cmd_chat.sor.forwarder import assert_isolated


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _refuse(reason: str) -> int:
    print(f"[RQ3 GO REFUSED] {reason}", file=sys.stderr)
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m cmd_chat.sor.rq3_confirmatory_run",
        description="RQ3 confirmatory battery: triple-locked human-gated LIVE data run.",
    )
    ap.add_argument("--out", default=f"output/sor-rq3-confirmatory/{_ts()}")
    ap.add_argument("--engine", default="docker")
    ap.add_argument("--order-seed", type=int, default=battery.S0)
    ap.add_argument("--r-runs", type=int, default=battery.R_RUNS)
    ap.add_argument("--c-circuits", type=int, default=battery.C_CIRCUITS)
    ap.add_argument("--pool-size", type=int, default=8)
    ap.add_argument("--hops", type=int, default=3)
    args = ap.parse_args(argv)

    # --- triple-lock ------------------------------------------------------- #
    if os.environ.get(OPERATOR_TOKEN_ENV) != "1":
        return _refuse(f"operator token missing (set {OPERATOR_TOKEN_ENV}=1)")
    if not verify_freeze():
        return _refuse("frozen LEAD prereg SHA-256 mismatch — refusing to run against an unfrozen prereg")
    try:
        assert_isolated(args.engine)
    except Exception as exc:  # noqa: BLE001
        return _refuse(f"containment: {exc}")

    from cmd_chat.sor import executor

    data_dir = Path(args.out) / "confirmatory-data"
    print(f"[RQ3 GO] all locks armed — collecting LIVE RQ3 battery "
          f"(selector arms × churn kp{battery.RQ3_KILL_PROB_PCT}s{battery.RQ3_CHURN_STEPS}, "
          f"R={args.r_runs} C={args.c_circuits}) into {data_dir}", flush=True)
    try:
        doc = executor.run_rq3_battery(
            data_dir, engine=args.engine, order_seed=args.order_seed,
            r_runs=args.r_runs, c_circuits=args.c_circuits,
            pool_size=args.pool_size, hops=args.hops, live=True,
        )
    except executor.ExecutorError as exc:
        return _refuse(f"executor refused (no fabricated DV): {exc}")

    print(f"[RQ3 GO] battery collected: {doc['n_runs']} runs "
          f"(measured_from={doc['measured_from']}) -> {doc['_results_path']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
