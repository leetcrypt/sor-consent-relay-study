# Note — the RQ2-P1 "shrink" is plausibly a unique-bridge instrument artifact

**Status:** on-record analysis note, 2026-07-21. Does **not** edit the frozen prereg or the
committed lead paper; it documents a mechanism concern for the record and motivates the
`rq2p3-mechanism-prereg.md` follow-up. Author: overseer, post-lead-paper review.

## The finding

The lead paper (RQ2-P1) reports federation **shrinks** the per-circuit anonymity set
(ΔH = −0.96 bits pooled; −3.63 bits bridge-federated-only, exploratory). Tracing the ratified
posterior mechanically shows this shrink is **largely forced by the instrument**, not by a
substantive funnelling phenomenon:

1. The adversary's observation is `exit_signature = (exit_house, bridge_label)`
   (`confirm_load_rq2.py:exit_signature`).
2. The anonymity set for circuit *i* is the distinct **entry** nodes among circuits sharing
   *i*'s signature (`observation_consistent_sizes`): `m_i = |{entry(j) : sig(j) == sig(i)}|`.
3. The bridge-federated instrument assigns a **fresh bridge per circuit seed**
   (`assembler.py:_bridge_label(seed)`), so **every circuit's `bridge_label` is unique** ⇒
   every `exit_signature` is unique ⇒ each group has size 1 ⇒ **`m_i = 1` ⇒ `H_i ≈ 0`.**

So bridge-federated collapses to near-zero entropy **because each circuit was handed its own
bridge**, making its signature a unique identifier. That is the *same* degeneracy that made
RQ2-P3 untestable (zero-variance concentration) — here it manifests as an artificially low H
that drives ΔH negative.

## Why this likely inverts under realistic bridge reuse

Introduce a finite shared bridge **pool**: many circuits share a bridge ⇒ shared signature ⇒
`m_i` = distinct entries across all of them ⇒ **larger set ⇒ higher H**. Under this posterior
a shared bridge behaves as a **mix**: more concentration plausibly *raises* anonymity — the
opposite of the naive "funnelling shrinks the set" story. The mechanism study
(`rq2p3-mechanism-prereg.md`) tests this **two-sided**; the mechanical prediction is mix
(ρ > 0), the naive prediction is funnel (ρ < 0).

## Consistency check against observed numbers

- Directory-federated cell (no bridge hop → `bridge_label = None`, shared signature):
  observed `rq2_anonymity_entropy_bits = 5.6439 = log₂(50)` — **maximal** entropy, all 50
  senders in the set. Confirms shared signatures give large sets.
- Bridge-federated (unique bridge per circuit): H ≈ 0, consistent with the exploratory
  ΔH = −3.63. The pooled −0.96 is the average of a high-H directory arm and a ≈0-H bridge arm.

## Integrity status

- The lead paper is **not wrong or dishonest**: §7 already flags RQ2 as conditional on the
  posterior construction and RQ2-P3 as an unresolved mechanism. This note **sharpens** that
  caveat from "conditional" to "the specific shrink magnitude is mechanically forced by the
  fresh-bridge instrument."
- **No silent edit** to the committed paper or frozen prereg. If the mechanism study confirms
  mix (ρ > 0), the honest outcome is a companion result that **qualifies/corrects** the lead
  RQ2-P1 headline — reported openly, per the null-results-are-results rail.
- This strengthens the body of work: it is exactly the kind of artifact a pre-registered,
  frozen-detector method is supposed to expose rather than bury.
