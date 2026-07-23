"""SS3 confirmatory loader — bind the immutable data dir to the frozen §6 gates.

**RQ1 only** (the fully frozen-specified half). This reconstructs the RQ1
``(entry-segment, exit-segment)`` circuit pairs from the **real per-hop pcaps**
the executor wrote (``executor.bin_pcap_bytes`` → ``detectors.score_matrix``),
never re-synthesising them, so :func:`confirm.rq1_p1_leak` scores measured data.
The candidate true pairing is the diagonal (same circuit); off-diagonal pairs are
unlinked — exactly the §4 "AUC over the (entry, exit) pair set, bootstrap over
circuit pairs" unit.

RQ1-P2 (padding efficacy) is wired here too: the frozen §6 **paired** bootstrap
pairs the bridge-on (no-pad) and bridge-on+padding arms **by run index** — the only
balanced pairing the R=30 interleaved design supports (freeze-derived; see
`docs/stage-05-rq1p2-pairing-clarification.md`). Each run index becomes one
`confirm.PairedCircuit` fed to the frozen `confirm.rq1_p2_padding`.

Split out (RQ2 lives in its own loader): **RQ2** — the per-circuit adversary
sender posterior (§3/§4) is reconstructed in `confirm_load_rq2.py` per the RATIFIED
stage-05 posterior clarification.

Blinding (prereg §2, binding): callers must **not** run this on a confirmatory
data dir until the full battery has completed — no inspection of intermediate
confirmatory results. Its plumbing is unit-tested on synthetic pcaps only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from cmd_chat.sor.analysis.detectors import score_matrix
from cmd_chat.sor.executor import DEFAULT_BINS, ExecutorError, bin_pcap_bytes

Pair = Tuple[float, bool]


def classify_run(run_dir: Path) -> Dict[str, object]:
    """Read the run's ``metrics.json`` for its cell identity + arm flags (both
    persisted by the executor). Raises if absent — a run is never guessed."""
    mp = Path(run_dir) / "metrics.json"
    if not mp.exists():
        raise ExecutorError(f"no metrics.json in {run_dir} — cannot classify run")
    d = json.loads(mp.read_text(encoding="utf-8"))
    return {
        "cell_id": d["cell_id"],
        "rq": d["rq"],
        "padding_applied": bool(d.get("padding_applied", False)),
        "run_index": d.get("run_index"),  # needed for the §6 RQ1-P2 run-index pairing
    }


def _circuit_series(run_dir: Path, bins: int, hops: int) -> Tuple[List[List[int]], List[List[int]]]:
    """Per-circuit (ingress=hop0, egress=last-hop) binned byte series, read from
    the REAL pcaps under ``run_dir/circuits/<id>/pcap/``. Refuses a circuit that
    is missing either endpoint pcap (never invents a flow)."""
    cdir = Path(run_dir) / "circuits"
    if not cdir.is_dir():
        raise ExecutorError(f"no circuits/ under {run_dir}")
    ingress: List[List[int]] = []
    egress: List[List[int]] = []
    for circuit in sorted(p for p in cdir.iterdir() if p.is_dir()):
        pdir = circuit / "pcap"
        ing, eg = pdir / "hop0.pcap", pdir / f"hop{hops - 1}.pcap"
        if not ing.exists() or not eg.exists():
            raise ExecutorError(f"missing ingress/egress pcap in {circuit}")
        ingress.append(bin_pcap_bytes(ing, bins))
        egress.append(bin_pcap_bytes(eg, bins))
    return ingress, egress


def reconstruct_run_pairs(run_dir: Path, *, bins: int = DEFAULT_BINS, hops: int = 3) -> List[Pair]:
    """The RQ1 pair set for one run: ``S[i][j] = pearson(ingress_i, egress_j)``
    over the run's circuits; the diagonal (``i == j``) is the linked (same-circuit)
    pair, every off-diagonal cell an unlinked pair. Measured from real pcaps."""
    ingress, egress = _circuit_series(Path(run_dir), bins, hops)
    scores = score_matrix(ingress, egress)
    n = len(scores)
    return [(scores[i][j], i == j) for i in range(n) for j in range(n)]


def collect_rq1_p1_pairs(data_dir: Path, *, bins: int = DEFAULT_BINS, hops: int = 3) -> List[Pair]:
    """Aggregate the RQ1-P1 leak-arm pairs across every **bridge-on (no padding)**
    run in the battery data dir — the pair set :func:`confirm.rq1_p1_leak` scores.
    Frozen cell ids end in ``bridge=on`` for the leak arm (``bridge=on+padding`` and
    ``bridge=off`` are excluded; ``padding_applied`` double-guards)."""
    pairs: List[Pair] = []
    for run_dir in sorted(p for p in Path(data_dir).iterdir() if p.is_dir()):
        if not (run_dir / "metrics.json").exists():
            continue
        info = classify_run(run_dir)
        if info["rq"] == "RQ1" and str(info["cell_id"]).endswith("bridge=on") and not info["padding_applied"]:
            pairs.extend(reconstruct_run_pairs(run_dir, bins=bins, hops=hops))
    return pairs


# --------------------------------------------------------------------------- #
# RQ1-P2 (padding efficacy) — the frozen §6 PAIRED bootstrap, paired BY RUN INDEX.
# Freeze-derived pairing (docs/stage-05-rq1p2-pairing-clarification.md): each run
# index i yields one confirm.PairedCircuit carrying that run's no-pad and +pad pair
# sets, fed to the frozen confirm.rq1_p2_padding. BLIND-GATED on real data.
# --------------------------------------------------------------------------- #
def _arm_pairs_by_run_index(
    data_dir: Path, *, want_padding: bool, bins: int, hops: int
) -> Dict[int, List[Pair]]:
    """Map run_index -> that run's RQ1 (entry,exit) pair set, for the bridge-on arm
    with (``want_padding``) or without padding. Runs missing a run_index in their
    persisted metrics.json are skipped (never guessed)."""
    out: Dict[int, List[Pair]] = {}
    for run_dir in sorted(p for p in Path(data_dir).iterdir() if p.is_dir()):
        if not (run_dir / "metrics.json").exists():
            continue
        info = classify_run(run_dir)
        if info["rq"] != "RQ1" or not str(info["cell_id"]).endswith(
            "bridge=on+padding" if want_padding else "bridge=on"
        ):
            continue
        if bool(info["padding_applied"]) != want_padding or info["run_index"] is None:
            continue
        out[int(info["run_index"])] = reconstruct_run_pairs(run_dir, bins=bins, hops=hops)
    return out


def collect_rq1_p2_paired(
    data_dir: Path, *, bins: int = DEFAULT_BINS, hops: int = 3
) -> List["PairedCircuit"]:
    """The RQ1-P2 paired units: one :class:`confirm.PairedCircuit` per run index
    present in **both** the bridge-on (no-pad) and bridge-on+padding arms — the
    freeze-derived run-index pairing (§6 "paired bootstrap"). Graceful: a run index
    missing an arm is simply not paired (the frozen R is not silently redefined);
    the caller reports inconclusive if too few paired units remain. BLIND-GATED —
    do not call on a confirmatory dir until the battery completes (prereg §2)."""
    from cmd_chat.sor.analysis.confirm import PairedCircuit

    nopad = _arm_pairs_by_run_index(Path(data_dir), want_padding=False, bins=bins, hops=hops)
    padded = _arm_pairs_by_run_index(Path(data_dir), want_padding=True, bins=bins, hops=hops)
    return [
        PairedCircuit(nopad_pairs=tuple(nopad[i]), pad_pairs=tuple(padded[i]))
        for i in sorted(set(nopad) & set(padded))
    ]


def per_run_delta_aucs(paired: Sequence["PairedCircuit"]) -> List[float]:
    """The per-run paired differences ``ΔAUC_i = AUC(no-pad,i) − AUC(+pad,i)`` — the
    auditable per-run diagnostic behind the §6 paired CI (one value per paired run
    index). Positive ⇒ padding lowered that run's linkability AUC."""
    from cmd_chat.sor.analysis.detectors import auc

    def _auc(pairs) -> float:
        pos = [s for s, linked in pairs if linked]
        neg = [s for s, linked in pairs if not linked]
        return auc(pos, neg)

    return [_auc(u.nopad_pairs) - _auc(u.pad_pairs) for u in paired]
