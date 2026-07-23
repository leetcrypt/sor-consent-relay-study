# Reproducing the SOR-Consent measurement

This artifact is designed so a reviewer can reproduce every headline number from
the sealed record. There are three levels of reproduction, from cheapest to most
expensive.

## 0. What is sealed (verify first)

Everything is anchored to a frozen pre-registration and a manifest of hashes:

- Frozen prereg: `prereg/sor-consent-prereg.md`
  SHA-256 `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`
  (recompute: `sha256sum prereg/sor-consent-prereg.md` and compare to
  `prereg/sor-consent-prereg.sha256`).
- Mechanism prereg (RQ2-P3′): `prereg/rq2p3-mechanism-prereg.md`
  SHA-256 `8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b`.
- Manifest of all 36,361 raw artifacts:
  `results/rq1-rq2-lead/SHA256SUMS.txt`
  (manifest-of-manifests digest
  `3fb67c7a9253c7f61f25a8432224decd85cff1b4baee8f6a1b60baa936707922`).

## 1. Seed reproduction (no data needed)

The whole run is driven by one base seed `S0 = 20260719` and the formula

```
seed = SHA256(S0 ‖ cell_id ‖ run_index)[:8]   # first 8 bytes as big-endian u64
```

implemented in `code/python/battery.py` (`derive_seed`). Given the same seed and
the same churn script, the circuit-build sequence is byte-identical. The freeze
report verified all **180/180** per-cell seeds recompute to their manifest values
(`results/rq1-rq2-lead/provenance.json` → `seed.verified`).

## 2. Re-run the analysis on the sealed metrics (cheap; minutes)

The confirmatory statistics (BCa 95% bootstrap CIs, Holm-7) are computed by the
frozen pipeline in `code/python/analysis/`. The aggregate inputs are published:

- `results/rq1-rq2-lead/analysis/stage06-results.json` — the frozen §6 pipeline output
- `results/rq2p3-mechanism/rq2p3-confirmatory-results.json`
- `results/rq3-churn/analysis/rq3-confirmatory-analysis.json`

Requirements: one x86_64 host, Python 3.10, `numpy`. The detectors and estimators
are calibrated **only** on the instrument-validation fixtures (known-linked
AUC ≈ 1.00, known-unlinked ≈ 0.50) — never fit to confirmatory-cell data.

**Expected headline numbers (must match bit-for-bit):**
- RQ1-P1 AUC = **0.4660**, BCa 95% CI **[0.4523, 0.4798]**
- RQ2-P1 ΔH = **−0.9587 bits**, CI **[−1.0559, −0.8641]**
- RQ2-P3′ Spearman ρ = **+0.62** (mix; CI > 0)

## 3. Re-run the full battery from the instrument (expensive; ~23 h)

Regenerating the raw pcaps/events requires the data plane:

- one x86_64 host with **Docker ≥ 27** (run recorded Docker 27.5.1),
- **Ollama** with `qwen2.5:3b` pulled (for the RQ3 selector arm; `$0`, local),
- the SOR instrument in `code/python/` + the Rust data-plane in `code/rust/`.

`confirmatory_run.py` regenerates the identical circuit-build sequence from the
seed. Every forwarder asserts `engine != local` and refuses to run on the host
(containment; see below). The battery window in the sealed run was
`2026-07-20T06:11:41Z → 2026-07-21T05:24:09Z` (~23 h) for 180 cells.

### Honest reproducibility caveat

The LLM selector arm replays via its committed **decision-log + `(seed, state-hash)`
cache**, *not* via independent model re-execution on other hardware. Re-running the
model on a different host may produce a different decision trace; the sealed
decision-log is the authoritative record for the reported RQ3 null.

## Containment (enforced in code, not just prose)

Every relay/forwarder process runs inside an isolated engine (Docker/Multipass);
the code asserts `engine != local` or refuses to run. Self-generated fixture
traffic only, on our own hosts. See `ETHICS-AND-CONTAINMENT.md` and
`results/rq1-rq2-lead/grid/device-map.json` (`self_traffic_only: true`,
`external_target: none`).
