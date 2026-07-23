# Ethics & containment

This work is a **defensive-security measurement**. We built a consent-gated onion
relay **as an instrument to measure a trust model's exposure**, not as a service
or a tool to provide anonymity to any third party. This document states the
containment law the experiment ran under; it maps 1:1 to the machine-checkable
provenance in `results/rq1-rq2-lead/grid/device-map.json`.

## Containment law (immutable; enforced in code)

1. **Isolated engine only.** Every forwarder/circuit process runs inside an
   isolated engine (Docker/Multipass). The code asserts `engine != local` or it
   refuses to run — **no forwarder ever runs on the host.**
2. **Self-generated traffic to our own fixtures only.** No real user traffic and
   no third-party data ever entered the instrument.
3. **Lab-only, our own devices.** The grid was one laptop (all forwarding hops) +
   our own VM churn fabric — all ours. Any external target, any live-network relay, or any
   local (non-isolated) forwarder is a **hard stop** requiring explicit human
   approval, and none occurred.
4. **Defensive-measurement framing is load-bearing** in the code, tests, comments,
   and commit history.

## Grid reality (disclosed)

- All relay hops ran as **isolated Docker containers on a single engine host**
  (the laptop; `isolated_engine_host_count = 1`, Docker 27.5.1).
- The two phones (`fp6`, `tril`) were **pinned as logical consenting-node labels, not
  forwarders**; they report `can_host_engine = false`, ran no forwarder, and carried no
  measured traffic (verified reachable only by a single grid-pin probe — see
  `PHONE-ROLE-AUDIT.md`). Turning a phone into a forwarder without an isolated engine
  would violate containment, so it was never done.
- Node distinctness is therefore **container-level** (≥ 3 distinct containers per
  circuit). Cross-machine timing effects are **out of scope** and named as future
  work, not claimed.

## Human subjects / data

- **No human subjects.** No third-party traffic, no PII.
- All artifacts are **self-generated fixtures**.
- The RQ3 agent selector used a **local, free** model (`qwen2.5:3b` via Ollama,
  `$0`); no paid frontier-model arm was run.

## Verifiable provenance

A reviewer can confirm "no external target / no real traffic" directly from the
sealed record:

```
results/rq1-rq2-lead/grid/device-map.json
  → "self_traffic_only": true
  → "external_target": "none"
  → "hops_run_in": "isolated docker containers only (never a phone/host forwarder)"
  → "isolated_engine_host_count": 1
```
