# SS2 raw-data freeze — integrity report

**Battery:** `output/sor-confirmatory/20260720T060132Z/confirmatory-data`
**Frozen prereg SHA-256:** `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`
**Frozen §4 sample:** R = 30 runs × C = 50 circuits per cell.
**Completion criterion (frozen):** 180 cells each carrying `metrics.json` — **MET**.

## Integrity assertions (all PASS)

| Check | Result |
|---|---|
| Cell dirs | **180** |
| Each has `metrics.json` | ✅ 180/180 |
| Each has `manifest.json` | ✅ 180/180 |
| Each has non-empty `circuits/` | ✅ 180/180 |
| Missing per-hop pcaps (hop0/1/2 × 9000 circuits) | **0** |
| Seed provenance `seed == SHA256(S0‖cell_id‖run_index)` (S0 = 20260719) | ✅ 180/180 match, 0 mismatch |

## Design-lattice mapping (R = 30 balance held)

RQ3 is **not** in the frozen lattice (dropped for the G4+RQ1+RQ2 lead paper). The
6 design cells (3 RQ1 arms + 3 RQ2 arms) each carry exactly R = 30 runs:

| cell_id | runs |
|---|---|
| RQ1/topo=1house/selector=static/bridge=off | 30 |
| RQ1/topo=1house/selector=static/bridge=on | 30 |
| RQ1/topo=1house/selector=static/bridge=on+padding | 30 |
| RQ2/bridge=off/selector=static/topo=1house-N | 30 |
| RQ2/bridge=off/selector=static/topo=bridge-federated | 30 |
| RQ2/bridge=off/selector=static/topo=directory-federated | 30 |

RQ counts: RQ1 = 90, RQ2 = 90. Selector = static; churn_schedule_id = none (RQ1/RQ2 use no churn).

## Immutability anchor

`SHA256SUMS.txt` — SHA-256 over **36361** raw artifacts (27000 per-hop pcaps +
9000 per-circuit `events.jsonl` + 361 `json` = 180 metrics + 180 manifest + 1),
sorted by relative path. Manifest-of-manifests digest:
`3fb67c7a9253c7f61f25a8432224decd85cff1b4baee8f6a1b60baa936707922`.

Raw `metrics.json` are **immutable** — not recomputed or edited in this stone.

## Provenance notes

- No aggregate `battery-results.json` was written (expected; **not** fabricated).
  Cell count 180/180 is the completion proxy.
- `engine.image_digest` was recorded `null` at run time (sor-hop image not
  digest-pinned by the executor); containment `engine != local` was asserted
  per-hop by `ForwarderPlan` at collection time.
- Battery window (mtime proxy): start `2026-07-20T06:11:41Z` → end
  `2026-07-21T05:24:09Z` (≈ 23h).

## Blinding

Blinding is **lifted for code-on-real-data**. SS2 touched **only**
structure/checksums/provenance — **no** RQ1/RQ2 inferential statistic (AUC / H /
CI) was computed, aggregated, or inspected. The first real inferential numbers
come from the frozen §6 pipeline in **SS3**, in one auditable pass.
