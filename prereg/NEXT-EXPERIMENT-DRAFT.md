# NEXT EXPERIMENT — DRAFT pre-registration (NOT frozen, NOT sealed)

> **Status: DRAFT.** This is a *plan*, not a sealed pre-registration. No confirmatory
> data may be collected against it until it is (a) reviewed, (b) frozen, and (c)
> SHA-256-hashed the same way the original `sor-consent-prereg.md` was. It is published
> here for transparency about the direction implied by `PHONE-ROLE-AUDIT.md`.

## 0. Why a *new* experiment (and not a re-run)

The original battery is **frozen and SHA-256-sealed** (`f22331a7…`). Re-running it and
choosing which run to report would be a garden-of-forking-paths violation and would
destroy the pre-registration guarantee. The phone audit changed **no measured number**
(the phones were never in the data path). So the correct response is not to re-run, but
to **pre-register a new study** that upgrades node-distinctness and adds a connectivity
failsafe — with its own fresh seal.

## 1. Two tracks

### Track B — container-simulated multi-pool houses (near-term, no hardware)

Replace the *logical phone labels* (house-B, house-C) with **genuinely distinct
container pools**: each house is an isolated Docker network hosting its own N node
containers, each with its own X25519/Ed25519 identity. This gives real, auditable
node-distinctness (network-namespace level) on the single laptop — no phone dependency —
while staying inside the containment law (`assert engine != local`, self-traffic only).

- **What it strengthens:** the "federation across distinct houses" claim becomes a
  measured property of separate container pools rather than a topology *label*.
- **What it still is NOT:** cross-machine / cross-city timing. That remains Track D.
- **Integrity boundary:** any numbers from Track B are **new**; they may be reported as
  **exploratory**, or promoted to confirmatory only under a fresh frozen prereg. They
  may **never** be merged into the sealed original battery.

### Track D — physical multi-host (later, needs hardware work)

Phones (or other hosts) as **real isolated-engine forwarders**,
`isolated_engine_host_count > 1`. Blocked today because `tril` is Termux with no Docker;
requires provisioning an isolated engine on each device. This is where cross-machine
timing claims (and a strong adversary) would finally be in scope.

## 2. Connectivity failsafe (folds in the "halt/pause on outage" idea)

A run-control watchdog that periodically probes every **required** node pool. On a
required pool becoming unreachable, one of two pre-registered policies fires — chosen in
advance, echoed into the manifest, **never** decided after seeing data:

- **HALT (default, integrity-first):** abort the run, mark the affected cell
  `inconclusive`, seal what exists. No optional-stopping bias because "inconclusive" is a
  pre-committed outcome, not a retry.
- **PAUSE-AND-RESUME (only if determinism is provable):** freeze the churn clock and the
  seed stream, wait for the pool to return (bounded timeout → escalate to HALT), then
  resume from the exact frozen state. Allowed **only** because the seed formula
  (`seed = SHA256(S0 ‖ cell_id ‖ run_index)`) makes the resumed sequence bit-identical.

Rationale: a failsafe only matters when connectivity feeds the measured data. In the
sealed study it did not (phones were non-forwarding). In Track B/D the pools **are**
load-bearing, so the watchdog protects real data integrity.

## 3. Design (to be finalized before freeze)

- **Detectors: reuse the frozen ones unchanged** (correlator/entropy/classifier),
  calibrated only on the instrument-validation fixtures — no fitting to Track B cells.
- **Seeds:** new base seed `S0'` (TBD), same per-cell formula.
- **Cells:** mirror the original RQ1/RQ2 cells but with container-pool houses; add a
  watchdog-policy factor {HALT, PAUSE} as a pre-registered control (not a hypothesis).
- **Gate:** all six instrument-validation gate items must pass on the new pools before
  any confirmatory cell runs; the watchdog must demonstrably HALT/PAUSE on an injected
  outage fixture and produce a deterministic resume (PAUSE) or clean inconclusive (HALT).

## 4. What must NOT happen (STOP conditions carried over)

- No confirmatory data before this draft is frozen + hashed and the gate is green.
- No external target, no live-network relay, no non-isolated forwarder.
- No paid frontier-model selector arm without explicit human approval.
- No editing of the original sealed prereg, manifests, or SHA256SUMS.
