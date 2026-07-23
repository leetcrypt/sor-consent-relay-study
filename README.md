# SOR-Consent: a pre-registered lab measurement of a consent-gated onion relay

**A defensive-security research artifact.** We built a small, consent-gated,
federated, nested-SSH "onion relay" **purely as a measurement instrument** — not
as a service and not as an anonymity product — so that a *pre-registered*
statistical battery could probe it. Everything ran in an isolated, lab-only
environment on our own hardware. Every headline number below is reproducible from
a single seed and is backed by a SHA-256-sealed artifact manifest.

> **Framing (load-bearing):** this repository is an *instrument to measure a trust
> model's exposure*, not a tool to provide anonymity to third parties. No real
> user data, no third-party traffic, no external target, no live-network relay.
> See [`ETHICS-AND-CONTAINMENT.md`](ETHICS-AND-CONTAINMENT.md).

📝 **Plain-language write-up:** [optinampout.com — SOR-Consent onion relay study](https://optinampout.com/blogs/2026-07-22-sor-consent-onion-relay-study)

## New here? Start with these

- **[`EXPERIMENT.md`](EXPERIMENT.md)** — the whole study explained step by step, in
  plain English, with exact numbers. **Start here if you want to understand what we did.**
- **[`GLOSSARY.md`](GLOSSARY.md)** — every technical term (AUC, entropy, mix vs funnel,
  pre-registration, ...) defined for a non-specialist. Keep it open as you read.
- **[`site/index.html`](site/index.html)** — a self-contained visual explainer with charts.

## Simple English explanation

We built a small system for sending messages through a chain of computers, where each
computer in the chain must **agree** ("consent") to carry your message — and where the
chain can only see its immediate neighbours, never the whole path (this is called
**onion routing**, the same idea behind Tor). We did **not** build it for people to use.
We built it as a **lab test rig** — like a crash-test car, not a car you drive — so we
could carefully *measure* three things and honestly report the answers, good or bad:

1. **Can an eavesdropper figure out who is talking to whom?** → **No.** Our attacker
   detector scored *worse than a coin flip* — it learned nothing useful.
2. **Does linking separate groups together give you a bigger crowd to hide in?** → At
   first it looked like the crowd got *smaller*, which was surprising. Looking closer, we
   found the real behaviour is a **good** kind of blending (a "mix") — the scary first
   number was a measurement artifact, and we report both.
3. **Can a small, free AI keep the chain healthy when computers keep dropping out,
   better than simple rules?** → **No.** The AI did not beat basic strategies, so we say
   so plainly.

The point of the project is **honesty by design**: before collecting any data, we locked
in *exactly* which tests we'd run and published a fingerprint of that plan, so we couldn't
secretly move the goalposts afterward. Out of **7** planned tests, **3** came out
positive — and we report the **4 that didn't**, because a "no" is a real scientific
result. Full walkthrough in **[`EXPERIMENT.md`](EXPERIMENT.md)**.

## What we asked, and what we found

| # | Question | Finding |
|---|----------|---------|
| **RQ1** | Can a shared "bridge" node linkably reveal who is talking to whom? | **No measurable leak.** Frozen flow-correlation detector scored **AUC = 0.466**, BCa 95% CI **[0.452, 0.480]** — *below* chance (0.5). |
| **RQ2** | Does federating houses together enlarge the crowd you can hide in? | As first instrumented it appeared to **shrink** (**ΔH = −0.96 bits**, CI [−1.06, −0.86]). A mechanism-corrected test showed the real behaviour is a **mix, not a funnel** (Spearman **ρ = +0.62**, CI > 0); the apparent shrink was an artifact of always picking a *unique* bridge. Reporting that correction is part of the finding. |
| **RQ3** | Can a small, free, locally-run AI agent keep a circuit healthy better than simple baselines when nodes keep dying? | **No.** The `$0` local `qwen2.5:3b` selector did **not** beat static/random baselines under churn, and its rebuild fingerprint was **not** distinct enough to certify (double-null; rebuild AUC 0.59, not excluded at n=30). We report this null. |

### Verdict

Of a **pre-registered family of 7** tests (Holm–Bonferroni corrected), **3 survive**
under the authoritative Holm-7 scorecard: **RQ1-P1** (anomaly-below-chance — *not*
a leak), **RQ2-P1** (a Holm-significant *negative*/shrink), and **RQ2-P3** (the
mechanism-corrected **mix** result). The headline of the work is scientific
integrity: **we committed to the outcomes in advance, including the null results,
and we report them plainly.**

## Scale of the sealed run

- **9,000** measured confirmatory circuits (180 cells × 30 runs × ... = R30×C50 lattice)
- **27,000** per-hop packet captures
- **36,361** individually SHA-256-sealed artifacts
- Fully seed-reproducible; isolated-engine-only; lab-only.

## Honest scope

This is a **lab measurement, not an internet-scale claim.** All relay hops ran as
**isolated Docker containers on a single engine host** (the laptop;
`isolated_engine_host_count = 1`); node distinctness is container-level. We do **not**
assume a global passive adversary. Physical multi-host distribution and a stronger
adversary are named future work, not claimed here.

> **Disclosed deviation.** Two phones were pinned in the grid inventory as logical
> consenting-node labels but were **non-forwarding** — `can_host_engine = false`, no
> forwarder, no measured traffic (all 27,000 pcaps came from laptop containers). They
> are not load-bearing to any finding; see [`PHONE-ROLE-AUDIT.md`](PHONE-ROLE-AUDIT.md)
> for the full evidenced record.

## Reproducibility spine

| Anchor | Value |
|--------|-------|
| Frozen pre-registration SHA-256 | `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b` |
| RQ2-P3 mechanism prereg SHA-256 | `8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b` |
| Base seed `S0` | `20260719` |
| Per-cell seed formula | `seed = SHA256(S0 ‖ cell_id ‖ run_index)[:8]` (big-endian u64) |
| Manifest-of-manifests digest | `3fb67c7a9253c7f61f25a8432224decd85cff1b4baee8f6a1b60baa936707922` |

See [`REPRODUCE.md`](REPRODUCE.md) for the step-by-step harness.

## Repository layout

```
EXPERIMENT.md          Plain-English, step-by-step walkthrough of the whole study
GLOSSARY.md            Every technical term defined for a non-specialist
REPRODUCE.md           How to reproduce every number from the sealed record
ETHICS-AND-CONTAINMENT.md  The safety/containment law the experiment ran under
paper/      Lead paper, companion methods, analysis notes, adversarial reviews
prereg/     Frozen pre-registrations + their SHA-256 stamps + design notes
code/
  python/   The SOR instrument + confirmatory/analysis pipeline (cmd_chat.sor)
  rust/      The nested-SSH data-plane + per-recipient X25519 consent crypto
results/     Sealed manifests, aggregate result JSONs, provenance, integrity,
            and the containment device-map — the pcaps themselves are offered
            on request (see below), verifiable against SHA256SUMS.
site/        A self-contained HTML explainer + the 6 story-slide figures
```

## Data availability

The **manifests, metrics, aggregate results, code, and provenance** are published
here. The **27,000 raw per-hop pcaps and 9,000 per-circuit event logs (~1.7 GB)**
are large and are **available on request** — every one of them is listed and hashed
in `results/rq1-rq2-lead/SHA256SUMS.txt`, so any copy can be verified bit-for-bit
against this sealed manifest.

## License

See [`LICENSE`](LICENSE).
