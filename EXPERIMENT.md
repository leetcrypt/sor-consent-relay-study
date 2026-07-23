# How the experiment was structured

This document explains **exactly** what we did, step by step, with no hand-waving.
It is written to be understandable without a science or security background. Terms in
**bold** are defined in [`GLOSSARY.md`](GLOSSARY.md).

---

## 1. The three questions

We asked three yes/no questions about a **consent-gated onion relay** and committed,
in advance, to reporting whatever the data said — including "no."

1. **RQ1 — Does a shared bridge leak who-talks-to-whom?**
   If many circuits share one **bridge** hop, can an eavesdropper link the sender to the
   receiver? We *hoped* the answer was "no."
2. **RQ2 — Does federating houses grow your hiding crowd?**
   A **"house"** is one independent **Hack House instance** — a self-contained chat-relay
   deployment (one community's server) with its own pool of relay nodes and its own keys;
   it is *not* a physical building. **Federating** houses links two or more of them so
   their relay pools combine into one bigger shared pool, with each circuit spanning ≥ 2
   houses (so no single house sees a whole path). Does that make your **anonymity set**
   (the crowd you blend into) bigger? We *hoped* "yes."
3. **RQ3 — Can a small free AI keep circuits healthy under churn?**
   When relays keep dying and being replaced (**churn**), does letting a tiny local AI
   pick the paths beat simple rules — *without* creating a recognizable fingerprint? We
   *hoped* "yes."

**The honest headline:** the answers were **no, no (with a twist), and no.** The value of
the work is that we *pre-committed* to reporting exactly that.

---

## 2. The equipment (the "grid")

- **One laptop** — the only machine that actually ran relay hops. Every hop ran as a
  separate **isolated Docker container** on this one laptop. Docker version 27.5.1.
- **Two phones** (`fp6`, `tril`) — they were **pinned in the grid inventory as logical
  consenting-node labels** (house-B, house-C) and were checked to be reachable once at
  grid-pin time. They report `can_host_engine = false`, so they **never forwarded** any
  traffic, and **no measured circuit traffic ever passed through them** — every packet
  capture came from a laptop container. (An honest audit of exactly what the phones did
  and did not do is in [`PHONE-ROLE-AUDIT.md`](PHONE-ROLE-AUDIT.md).)
- **The "houses" were logical groupings on this grid, not separate machines:**
  **house-A** = the laptop's pool of relay containers, **house-B** = phone `fp6`, and
  **house-C** = phone `tril` (both as consenting nodes). So "federating houses" here means
  combining these logical relay pools — the forwarding hops themselves were all containers
  on the one laptop.
- **Containment:** every hop process asserts `engine != local` — it *refuses to run*
  unless it is inside a sandbox. No real internet traffic, no third parties, ever. All
  traffic was test data we generated ourselves.

> **What this means for the results:** the different "hops" were *different containers on
> one laptop*, not different physical machines in different cities. So we do **not** claim
> anything about real-world, cross-city network timing. That is honestly disclosed and
> named as future work — see [`ETHICS-AND-CONTAINMENT.md`](ETHICS-AND-CONTAINMENT.md).

---

## 3. What one measurement looks like (the units)

Read these nested units from smallest to largest — they are the source of the
"9,000 / 27,000 / 36,361" numbers:

| Unit | What it is | Count |
|------|-----------|-------|
| **Hop** | one relay container in a chain | 3 per circuit |
| **Circuit** | one full 3-hop chain a message travels | — |
| **Run** | one seeded repetition that builds **50 circuits** (C = 50) | 50 circuits each |
| **Condition (design cell)** | one specific experimental setup, repeated **30 times** (R = 30) | 30 runs each |
| **Battery** | all conditions together | see below |

**The arithmetic (all reproducible from one seed):**

- **6 conditions** × **30 runs each** = **180 runs**
- **180 runs** × **50 circuits each** = **9,000 circuits**
- **9,000 circuits** × **3 hops each** = **27,000 packet captures** (**pcaps**)
- Plus 9,000 event logs + 361 metric/manifest files = **36,361 sealed files** in total,
  each individually SHA-256-fingerprinted.

---

## 4. The 6 conditions (what we varied)

The main "lead" study held everything fixed except one knob at a time. All conditions
used a single house with a **static** selector unless noted.

**RQ1 conditions — is there a leak, and does padding help?**
| Condition | Bridge | Cover padding |
|-----------|--------|---------------|
| RQ1-a | off | none |
| RQ1-b | **on** | none |
| RQ1-c | **on** | **on** |

**RQ2 conditions — does federation grow the crowd?**
| Condition | Topology |
|-----------|----------|
| RQ2-a | single house (baseline crowd) |
| RQ2-b | **bridge-federated** (houses share via a bridge) |
| RQ2-c | **directory-federated** (houses share via a directory) |

**RQ3** was run as its **own separate battery** (not part of the 6-cell lead lattice),
comparing three selectors — **static**, **random**, and the **AI agent** (`qwen2.5:3b`,
a free local model, temperature 0) — under a fixed churn schedule.

---

## 5. The measuring tools (detectors) and how we kept them honest

Three "detectors" turn raw traffic into numbers. **Crucially, each was calibrated only
on known test cases *before* touching real experiment data** — never tuned to make the
results look better:

1. **Flow-correlation detector → an AUC score.** Calibrated to score **1.00** on
   known-linked pairs and **0.50** on known-unlinked pairs. Only after passing that check
   did we let it read the real traffic.
2. **Entropy estimator → crowd size in bits (H).** Verified to return exactly
   `log2(N)` bits for `N` equally-likely senders.
3. **Rebuild-timing classifier → an AUC score** (for RQ3's fingerprint question), also
   fixture-calibrated before use.

---

## 6. The statistics (in plain terms)

- Every result is reported as an **effect size with a 95% confidence interval** (a
  range), computed by **bootstrap (BCa)** resampling — never a lone p-value.
- Because we ran **7 tests**, we applied the **Holm–Bonferroni correction**, a standard
  conservative adjustment so that random flukes don't get mistaken for real effects.
- A test "**survives**" only if its confidence interval clears the pre-registered bar
  *after* that correction.

---

## 7. The seven pre-registered tests and their verdicts

This is the complete, frozen **family of 7**. "Survived?" is under the authoritative
Holm-7 correction.

| Test | Plain-English question | Result | Survived? |
|------|------------------------|--------|-----------|
| **RQ1-P1** | Does the bridge leak linkability? | **AUC 0.466** (CI [0.452, 0.480]) — *below* a coin flip → **no leak** | ✅ yes* |
| **RQ1-P2** | Does cover padding reduce a leak? | ΔAUC +0.011 (CI crosses 0) → **no effect** (nothing to hide) | ❌ no |
| **RQ2-P1** | Does federation grow the crowd? | **ΔH = −0.96 bits** (CI [−1.06, −0.86]) → crowd *shrank* (a clear **negative**) | ✅ yes |
| **RQ2-P3** | Is the bridge a funnel or a mix? | **mix** — concentration *raises* anonymity (Spearman ρ = **+0.62**, CI > 0) | ✅ yes |
| **RQ3-P1-perf** | Does the AI beat static/random on throughput? | needed +10 pp margin; **not met** (every selector healed ~all churn) | ❌ no |
| **RQ3-P1-latency** | Does the AI keep added delay ≤ 100 ms? | inconclusive on this grid | ❌ no |
| **RQ3-P2** | Is the AI's rebuild pattern *un*-fingerprintable? | rebuild AUC ~0.59; could **not** certify ≤ 0.60 at n = 30 | ❌ no |

`*` RQ1-P1 "survives" by rejecting the coin-flip in the **wrong direction** (below 0.5),
which the pre-registered rule correctly refuses to call a leak. It is evidence of
**no leak**, not of a leak.

**Score: 3 of 7 survived** — RQ1-P1, RQ2-P1, RQ2-P3.

---

## 8. Why the "mix, not funnel" twist matters (RQ2)

RQ2 first looked like *bad* news: federation **shrank** the crowd by 0.96 bits. But when
we looked at *why*, we found the shrink was an artifact of always picking a **unique**
bridge for each circuit. Re-instrumented as a **finite shared pool**, the same design
behaves like a **mix** (ρ = +0.62): concentrating circuits through a few shared bridges
makes them look alike and *grows* the effective crowd. Reporting that mechanism
correction — rather than just the scary first number — is part of the finding. Details in
[`paper/note-unique-bridge-artifact.md`](paper/note-unique-bridge-artifact.md).

---

## 9. What this study does *not* claim

- Not internet-scale. Hops were containers on **one** laptop, not machines spread across
  the world.
- Not a claim against a **global** eavesdropper. We modelled a **local** observer with one
  (and, as future work, a stronger) correlation detector.
- Not a privacy product. This is a **measurement instrument**, full stop.

For how to reproduce every number yourself, see [`REPRODUCE.md`](REPRODUCE.md).
