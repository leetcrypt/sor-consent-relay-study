"""RQ1+RQ2 confirmatory battery — start-line preflight + guarded launcher.

This is the single operator entrypoint. Run with **no flags** it performs the
*safe* start-line **preflight** and writes auditable artifacts, then prints a
GO/NO-GO summary and the exact launch command — it collects **no** confirmatory
data:

  * §5 instrument-validation gate re-confirmation (``gate.run_gate``);
  * grid inventory + containment pin (``grid.write_device_map``);
  * frozen §2 cell plan + randomized/interleaved schedule (``battery.write_cell_plan``);
  * a 1-cell × 2-run DRY provenance pass on fixtures (``battery.dry_pass``).

The live per-cell condition assembler is now wired (``sor.assembler``): each cell
maps to a genuinely distinct, condition-encoding, isolation-gated circuit (RQ1
bridge-on / on+padding arms actually insert a bridge hop + PADDING stream; RQ2
bridge-/directory-federated topologies genuinely span >= 2 houses). The preflight
proves this on FIXTURES (``battery.assembler_dry_check`` — plans only, no traffic).

The **immutable confirmatory data run on the real grid is the human gate**
(CLAUDE.md §Stop, GOAL envelope (b)). ``--operator-go`` is triple-locked — it
requires the ``SOR_CONFIRMATORY_GO=1`` operator token, a verified frozen-prereg
SHA-256, and an isolated engine — plus a green preflight and a full grid. When all
of those hold, this IS the operator's explicit GO and the wired data-collection
executor (``sor.executor``) collects the battery for real: it stands up each cell's
assembled circuit on the isolated engine, moves only self-generated fixture bytes,
and **measures the DVs from the real pcaps** (``executor.run_battery(live=True)``).
The executor refuses to emit any DV it did not measure — it never fabricates.

Containment is load-bearing: nothing here forwards real/third-party traffic,
touches an external target, or runs a forwarder on the host.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from cmd_chat.sor import battery, gate, grid
from cmd_chat.sor.forwarder import assert_isolated

# The frozen prereg (read-only source of truth) and its pinned SHA-256. A GO is
# refused unless the on-disk prereg still hashes to this — no confirmatory run
# against an unfrozen/edited prereg.
FROZEN_PREREG = Path.home() / "coding/sci-method/stages/03-design/output/sor-consent-prereg.md"
FROZEN_PREREG_SHA256 = "f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b"

OPERATOR_TOKEN_ENV = "SOR_CONFIRMATORY_GO"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def verify_freeze() -> bool:
    """True iff the on-disk frozen prereg still matches its pinned SHA-256."""
    try:
        got = hashlib.sha256(FROZEN_PREREG.read_bytes()).hexdigest()
    except OSError:
        return False
    return got == FROZEN_PREREG_SHA256


def preflight(out_dir: Path, *, order_seed: int = battery.S0, allow_live_gate: bool = True) -> Dict[str, Any]:
    """Run the safe start-line preflight and write artifacts under ``out_dir``.
    Collects no confirmatory data. Returns a summary with a GO/NO-GO verdict."""
    out_dir = Path(out_dir)
    g = gate.run_gate(out_dir / "gate", allow_live=allow_live_gate)
    dm = grid.write_device_map(out_dir / "grid")
    plan_path = battery.write_cell_plan(out_dir / "plan", order_seed=order_seed)
    dp = battery.dry_pass(out_dir / "dry", runs=2)
    asm = battery.assembler_dry_check(out_dir / "assembler")

    ready = bool(
        g["all_green"]
        and dm["topology_matchedN_honourable"]
        and dp["all_sha_match"] and dp["all_seed_reproduces"] and dp["distinct_seeds"]
        and asm["all_green"]
        and verify_freeze()
    )
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "out_dir": str(out_dir),
        "gate_all_green": g["all_green"],
        "gate_offline_green": g["offline_items_green"],
        "grid_reachable": dm["reachable_count"],
        "grid_engine_hosts": dm["isolated_engine_host_count"],
        "grid_down": dm["devices_down"],
        "grid_honourable": dm["topology_matchedN_honourable"],
        "grid_full": len(dm["devices_down"]) == 0,
        "cell_plan": str(plan_path),
        "dry_ok": dp["all_sha_match"] and dp["all_seed_reproduces"] and dp["distinct_seeds"],
        "assembler_ok": asm["all_green"],
        "assembler_distinct": asm["distinct_fingerprints"],
        "assembler_isolation_gated": asm["all_isolation_gated"],
        "freeze_ok": verify_freeze(),
        "preflight_ready": ready,
    }


def _print_summary(s: Dict[str, Any]) -> None:
    print(f"[preflight] artifacts -> {s['out_dir']}")
    print(f"[preflight] gate all_green={s['gate_all_green']} "
          f"(offline={s['gate_offline_green']})")
    print(f"[preflight] grid reachable={s['grid_reachable']} "
          f"engine_hosts={s['grid_engine_hosts']} down={s['grid_down']} "
          f"honourable={s['grid_honourable']}")
    print(f"[preflight] dry_ok={s['dry_ok']} freeze_ok={s['freeze_ok']}")
    print(f"[preflight] assembler_ok={s['assembler_ok']} "
          f"(distinct={s['assembler_distinct']} isolation_gated={s['assembler_isolation_gated']})")
    print(f"[preflight] grid_full={s['grid_full']} READY={s['preflight_ready']}")


def _refuse_go(reason: str) -> int:
    print(f"[GO REFUSED] {reason}", file=sys.stderr)
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m cmd_chat.sor.confirmatory_run",
        description="RQ1+RQ2 confirmatory battery: safe preflight by default; "
                    "--operator-go is the human-gated immutable data run.",
    )
    ap.add_argument("--out", default=f"output/sor-confirmatory/{_ts()}",
                    help="preflight artifact dir (default: timestamped)")
    ap.add_argument("--order-seed", type=int, default=battery.S0,
                    help="measurement-side schedule ordering seed (default S0)")
    ap.add_argument("--engine", default="docker", help="isolated engine (default docker)")
    ap.add_argument("--operator-go", action="store_true",
                    help="attempt the human-gated confirmatory data run (triple-locked)")
    ap.add_argument("--r-runs", type=int, default=battery.R_RUNS,
                    help=f"runs per cell (frozen §4 default R={battery.R_RUNS})")
    ap.add_argument("--c-circuits", type=int, default=battery.C_CIRCUITS,
                    help=f"circuits per run (frozen §4 default C={battery.C_CIRCUITS})")
    ap.add_argument("--hops", type=int, default=3, help="hops per circuit (default 3)")
    ap.add_argument("--bins", type=int, default=32, help="pcap time-bins for the correlator")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    summary = preflight(out_dir, order_seed=args.order_seed)
    _print_summary(summary)

    go_cmd = (f"{OPERATOR_TOKEN_ENV}=1 python -m cmd_chat.sor.confirmatory_run "
              f"--operator-go --engine {args.engine}")

    if not args.operator_go:
        print("\n[held] preflight only — no confirmatory data collected.")
        print(f"[held] the immutable data run is the human gate. GO command:\n    {go_cmd}")
        return 0

    # --- triple-locked GO path (human gate) --------------------------------- #
    if os.environ.get(OPERATOR_TOKEN_ENV) != "1":
        return _refuse_go(f"operator token missing (set {OPERATOR_TOKEN_ENV}=1)")
    if not verify_freeze():
        return _refuse_go("frozen prereg SHA-256 mismatch — refusing to run against an unfrozen prereg")
    try:
        assert_isolated(args.engine)
    except Exception as exc:  # noqa: BLE001
        return _refuse_go(f"containment: {exc}")
    if not summary["preflight_ready"]:
        return _refuse_go("preflight not fully green — resolve NO-GO items before a data run")

    # Triple-lock passes and the live per-cell condition assembler is wired +
    # fixture-validated (assembler_ok). The one remaining gate is physical: the
    # confirmatory battery HOLDS until the full grid is up. The operator is
    # bringing the 3rd phone online; until every device is reachable this launcher
    # refuses to launch a data run on a degraded grid rather than fabricate cells.
    if not summary["grid_full"]:
        return _refuse_go(
            "grid completing: confirmatory battery holds until the full physical "
            f"grid is up (devices down: {summary['grid_down']}). The live per-cell "
            "assembler is wired + fixture-validated; the operator is bringing the "
            "3rd phone online. Re-run --operator-go once the grid is complete."
        )

    # Full grid + all three locks + green preflight + the operator token: this IS
    # the operator's explicit GO. Collect the confirmatory battery for real — the
    # executor stands up each cell's assembled circuit on the isolated engine, moves
    # only self-generated fixture bytes, and measures the DVs from the real pcaps.
    # It refuses to emit any DV it did not measure (never fabricates).
    from cmd_chat.sor import executor

    data_dir = out_dir / "confirmatory-data"
    print(f"\n[GO] all locks armed + grid full — collecting confirmatory battery "
          f"(R={args.r_runs} C={args.c_circuits} hops={args.hops}) into {data_dir}")
    try:
        doc = executor.run_battery(
            data_dir, engine=args.engine, order_seed=args.order_seed,
            r_runs=args.r_runs, c_circuits=args.c_circuits, hops=args.hops,
            bins=args.bins, live=True,
        )
    except executor.ExecutorError as exc:
        return _refuse_go(f"executor refused (no fabricated DV): {exc}")
    except Exception as exc:  # noqa: BLE001
        return _refuse_go(f"executor error during live collection: {exc}")

    print(f"[GO] confirmatory battery collected: {doc['n_runs']} runs "
          f"(measured_from={doc['measured_from']}) -> {doc['_results_path']}")
    print("[GO] next: analysis/confirm.py CI-gate + Holm (family_size=7, report 4) "
          "over the reported RQ1/RQ2 DVs.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
