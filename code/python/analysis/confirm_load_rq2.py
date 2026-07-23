"""SS3 RQ2 offline loader — the per-circuit adversary sender-posterior, per the
**RATIFIED** stage-05 clarification (``docs/stage-05-rq2-posterior-clarification.md``,
operator-ratified 2026-07-20 while blind to RQ2 data).

This reconstructs each circuit's condition-encoding ``CircuitSpec`` **offline** from
its per-circuit seed (deterministic :func:`assembler.assemble`), derives the
**observation-consistent anonymity set** A_i (uniform / max-entropy posterior), and
yields the exact inputs the frozen §6 RQ2 tests consume:

  * **RQ2-P1 (ΔH):** per-circuit sender-posterior **count vectors** (``[1]*m_i``)
    for the federated and matched-N single-house arms → :func:`confirm.rq2_p1_delta_h`.
  * **RQ2-P3 (funnel):** per-circuit **(bridge-concentration c_i, entropy H_i)**
    over the willing-bridge arm → :func:`confirm.rq2_p3_funnel`.

**Ratified rule (substance frozen in the clarification; this is only its mechanical
implementation — no new modelling choice is introduced here):**

  * The adversary observes the **exit-signature** the circuit leaves the federation
    through: ``(exit-house, bridge-label)``. It does *not* observe the true entry.
  * A_i = the consenting **entry-node candidates observation-consistent** with that
    signature — the distinct realized entry nodes among the run's circuits sharing
    circuit i's exit-signature. The **single-house arm** is the whole pool
    (``A_i = matched N``): no federation observation narrows it (ratified doc).
  * **Uniform mass** over A_i (max-entropy, the standard [Serjantov2002]/[Diaz2002]
    anonymity-set assumption) → count vector ``[1]*m_i``. Per-circuit entropy
    ``H_i = miller_madow_entropy_bits([1]*m_i) = log2 m_i + (m_i-1)/(2 m_i ln2)``,
    the §5-calibrated estimator (gate item 4). ``S_i = 2^H_i`` [Serjantov2002];
    ``d_i = H_i / log2 N`` [Diaz2002], N = matched total consenting nodes.

**BLINDING (prereg §2, binding).** Ratification unblocks the **CODE, not the
results**. Callers must NOT run :func:`collect_rq2_p1_arms` / :func:`collect_rq2_p3`
on a confirmatory data dir until the full battery has **completed**
(``battery-results.json`` present, or all cell-runs carry ``metrics.json``). The
core reconstruction below is unit-tested on **synthetic** specs / seeds only — no
confirmatory record is read to develop or test it.

**Instrument caveat (for the SS5 review, not a loader defect).** The bridge-
federated assembler derives a *fresh* bridge label per circuit seed
(``assembler._bridge_label(cseed)``), so willing-bridge reuse is minimal and the
P3 concentration distribution may be near-degenerate as-instrumented; that is an
honest property of the built instrument and, if the sealed data bears it out, an
inconclusive P3 is a legitimate (reported) outcome — the loader does not "fix" it.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from cmd_chat.sor.analysis.stats import miller_madow_entropy_bits
from cmd_chat.sor.assembler import CircuitSpec, assemble

# --------------------------------------------------------------------------- #
# Per-circuit observable projections (what the exit-adversary sees / does not).
# --------------------------------------------------------------------------- #
def entry_label(spec: CircuitSpec) -> str:
    """The circuit's true entry node — the sender the adversary is trying to
    identify (NOT observed; it is what the anonymity set conceals)."""
    return spec.hops[0].node_label


def bridge_label(spec: CircuitSpec) -> Optional[str]:
    """The willing-bridge node the circuit crosses, if any (``None`` for a
    directory-federated / single-house circuit that carries no bridge hop)."""
    for h in spec.hops:
        if h.is_bridge:
            return h.node_label
    return None


def exit_signature(spec: CircuitSpec) -> Tuple[str, Optional[str]]:
    """The exit-signature the adversary observes: the (exit-house, bridge-label)
    through which the circuit leaves the federation."""
    return (spec.hops[-1].house, bridge_label(spec))


def _is_single_house(spec: CircuitSpec) -> bool:
    """The matched-N single-house arm — no federation observation narrows the pool
    (ratified doc: A_i = all N)."""
    return spec.topology == "1house-N"


# --------------------------------------------------------------------------- #
# Observation-consistent anonymity set A_i (the ratified construction).
# --------------------------------------------------------------------------- #
def observation_consistent_sizes(specs: Sequence[CircuitSpec]) -> List[int]:
    """Per-circuit anonymity-set size ``m_i = |A_i|`` for one run's circuits.

    Single-house arm: ``m_i = matched N`` for every circuit (whole pool; no
    narrowing). Federated arms: group the run's circuits by observed exit-signature
    and set ``m_i`` = the number of **distinct realized entry nodes** in circuit
    i's group — the consenting senders indistinguishable to the exit-adversary."""
    if not specs:
        return []
    if all(_is_single_house(s) for s in specs):
        return [s.matched_n for s in specs]

    groups: dict = {}
    for s in specs:
        groups.setdefault(exit_signature(s), set()).add(entry_label(s))
    return [len(groups[exit_signature(s)]) for s in specs]


def per_circuit_posteriors(specs: Sequence[CircuitSpec]) -> List[List[int]]:
    """Per-circuit uniform sender-posterior COUNT VECTORS ``[1]*m_i`` (max-entropy
    over A_i) — the input rows for :func:`confirm.rq2_p1_delta_h`."""
    return [[1] * m for m in observation_consistent_sizes(specs)]


def per_circuit_entropy(specs: Sequence[CircuitSpec]) -> List[float]:
    """Per-circuit Miller–Madow entropy ``H_i`` (bits) of the uniform posterior —
    the §5-calibrated estimator applied to ``[1]*m_i``."""
    return [miller_madow_entropy_bits([1] * m) for m in observation_consistent_sizes(specs)]


# --------------------------------------------------------------------------- #
# Willing-bridge concentration (RQ2-P3 mechanism).
# --------------------------------------------------------------------------- #
def bridge_concentration(specs: Sequence[CircuitSpec]) -> List[Optional[float]]:
    """Per-circuit willing-bridge concentration ``c_i`` = the fraction of the run's
    **bridge-bearing** circuits that route through the SAME willing bridge as
    circuit i. ``None`` for a circuit that carries no bridge (excluded from the P3
    funnel test, which is defined on the willing-bridge arm). Summing the top-3
    distinct-bridge shares recovers the frozen §6 "top-k=3 bridge concentration"."""
    bridged = [s for s in specs if bridge_label(s) is not None]
    total = len(bridged)
    if total == 0:
        return [None for _ in specs]
    counts: dict = {}
    for s in bridged:
        b = bridge_label(s)
        counts[b] = counts.get(b, 0) + 1
    out: List[Optional[float]] = []
    for s in specs:
        b = bridge_label(s)
        out.append(None if b is None else counts[b] / total)
    return out


def top_k_bridge_concentration(specs: Sequence[CircuitSpec], k: int = 3) -> float:
    """Run-level "fraction of circuits through the top-k willing bridges" (frozen
    §6, k=3) — reported alongside the per-circuit series for completeness."""
    bridged = [s for s in specs if bridge_label(s) is not None]
    total = len(bridged)
    if total == 0:
        return 0.0
    counts: dict = {}
    for s in bridged:
        b = bridge_label(s)
        counts[b] = counts.get(b, 0) + 1
    top = sorted(counts.values(), reverse=True)[:k]
    return sum(top) / total


def rq2_p3_pairs(specs: Sequence[CircuitSpec]) -> Tuple[List[float], List[float]]:
    """The parallel ``(concentration, per_circuit_h)`` series over the willing-bridge
    circuits of a run — the two arguments of :func:`confirm.rq2_p3_funnel`. Circuits
    with no bridge are dropped (concentration undefined there)."""
    conc = bridge_concentration(specs)
    ent = per_circuit_entropy(specs)
    xs: List[float] = []
    ys: List[float] = []
    for c, h in zip(conc, ent):
        if c is not None:
            xs.append(c)
            ys.append(h)
    return xs, ys


# --------------------------------------------------------------------------- #
# Offline reconstruction from the immutable raw records (per_circuit_seeds).
# --------------------------------------------------------------------------- #
def reconstruct_run(cell, per_circuit_seeds: Sequence[int], *,
                    engine: str = "docker", hops: int = 3) -> List[CircuitSpec]:
    """Rebuild a run's ``C`` circuit specs OFFLINE from the immutable
    ``per_circuit_seeds`` the executor persisted: ``assemble`` is deterministic, so
    each seed reproduces its circuit's path / house / bridge / consenting pool with
    no live circuit. This is why the running battery is not wasted under the
    ratified rule — RQ2 is recomputable from the sealed records."""
    return [assemble(cell, int(cseed), engine=engine, hops=hops) for cseed in per_circuit_seeds]


# --------------------------------------------------------------------------- #
# Real-data collectors — BLIND-GATED: do NOT call until the battery COMPLETES.
# --------------------------------------------------------------------------- #
def _cells_by_id():
    from cmd_chat.sor.battery import enumerate_cells

    return {c.cell_id: c for c in enumerate_cells()}


def collect_rq2_p1_arms(data_dir, *, engine: str = "docker", hops: int = 3
                        ) -> Tuple[List[List[int]], List[List[int]]]:
    """Aggregate the RQ2-P1 arms across the sealed battery: return
    ``(federated_vectors, single_house_vectors)`` — per-circuit posterior count
    vectors for the two federated cells and the matched-N single-house cell,
    reconstructed offline from each run's ``per_circuit_seeds``.

    **BLIND-GATED (prereg §2).** Reads confirmatory records; must be called only
    AFTER the full battery has completed. Not exercised by the synthetic tests."""
    import json
    from pathlib import Path

    doc = json.loads((Path(data_dir) / "battery-results.json").read_text(encoding="utf-8"))
    cells = _cells_by_id()
    federated: List[List[int]] = []
    single: List[List[int]] = []
    for run in doc.get("runs", []):
        cell = cells.get(run["cell_id"])
        if cell is None or cell.rq != "RQ2":
            continue
        specs = reconstruct_run(cell, run.get("per_circuit_seeds", []), engine=engine, hops=hops)
        vectors = per_circuit_posteriors(specs)
        topo = cell.factors.get("topology")
        if topo == "1house-N":
            single.extend(vectors)
        elif topo in ("bridge-federated", "directory-federated"):
            federated.extend(vectors)
    return federated, single


def collect_rq2_p3(data_dir, *, engine: str = "docker", hops: int = 3
                   ) -> Tuple[List[float], List[float]]:
    """Aggregate the RQ2-P3 ``(concentration, per_circuit_h)`` series over the
    willing-bridge (bridge-federated) circuits of the sealed battery.

    **BLIND-GATED (prereg §2).** Reads confirmatory records; call only AFTER the
    battery completes. Not exercised by the synthetic tests."""
    import json
    from pathlib import Path

    doc = json.loads((Path(data_dir) / "battery-results.json").read_text(encoding="utf-8"))
    cells = _cells_by_id()
    conc: List[float] = []
    ent: List[float] = []
    for run in doc.get("runs", []):
        cell = cells.get(run["cell_id"])
        if cell is None or cell.rq != "RQ2":
            continue
        if cell.factors.get("topology") != "bridge-federated":
            continue
        specs = reconstruct_run(cell, run.get("per_circuit_seeds", []), engine=engine, hops=hops)
        xs, ys = rq2_p3_pairs(specs)
        conc.extend(xs)
        ent.extend(ys)
    return conc, ent
