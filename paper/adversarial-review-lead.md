# Stage-08 adversarial review (SS5) — red-team of the filled lead paper

**Status: DONE (self-adversarial pass over the SS3 numbers + the SS4-filled paper).**
This is an internal integrity red-team, not a new analysis. It runs ONLY on already-frozen
artifacts (`docs/stage-06-analysis.md`, `stage06-results.json`, `docs/stage-07-paper-draft.md`);
it computes no new statistic, touches no raw data, and does not edit the frozen prereg
(SHA `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`).

## Checks performed

1. **Number fidelity (paper ⟷ results JSON).** Every quantitative claim in the abstract, §1,
   §5, §5.4 table, and the exploratory note was matched against
   `stage06-results.json`. All agree to the reported precision:
   - RQ1-P1 AUC 0.4660, CI [0.4523, 0.4798]; RQ1-P2 ΔAUC +0.0113, CI [−0.0025, +0.0234],
     raw p 0.091, Holm-adj 0.456; RQ2-P1 ΔH −0.9587, CI [−1.0559, −0.8641]; RQ2-P3 ρ 0.0;
     exploratory bridge-fed-only ΔH −3.63; calibration linked 1.0000 / unlinked 0.5036;
     n = 75000 pairs (1500 linked), 30 paired runs, 3000 federated / 1500 single-house / 1500
     bridge-fed circuits. **PASS.**
2. **Holm arithmetic.** Family = 7, report 4, ascending raw p → multipliers 7,6,5,4; adjusted
   p = 0,0,0.456,1.0 with monotone enforcement; only RQ1-P1 + RQ2-P1 survive @ α=.05.
   Conservative embedding (reported tests assigned the smallest ranks / largest multipliers)
   is stated and is the *more* conservative choice. **PASS.**
3. **Spin / over-claim.** RQ1-P1 is reported as "no measurable leak" (a below-chance rejection is
   explicitly NOT called a leak); RQ2-P1 is reported as an honest negative "with equal prominence"
   and is not re-framed as federation "helping"; §6 scopes all claims to the lab
   instrument/topology and disclaims internet-scale and stronger-adversary generality. No
   re-slicing, no post-hoc subgroups. **PASS.**
4. **Blinding integrity.** Header records §1–4/7 blind-authored and §5–6 filled ONCE post-seal
   from the single §6 pass; consistent with git history (SS4 fill follows SS3 seal). **PASS.**
5. **Method-substitution.** The RQ1 fast bootstraps are disclosed and asserted bit-for-bit equal
   to the frozen `stats.bootstrap_ci` (committed `--verify`, 1e-12). Point estimates, CI gates,
   and decisions are unchanged. **PASS.**

## Defect found and corrected (1)

- **Incorrect mechanism attribution for RQ1-P1's below-chance AUC.** Both
  `docs/stage-06-analysis.md` and the SS4 paper originally attributed the marginally-below-chance
  AUC to "the bridge hop's padding stream flattening the linked-pair temporal profile." This is
  **false for the RQ1-P1 arm**: `assembler.py` sets `padding_applied = (bridge == "on+padding")`,
  so the bridge-on **no-pad** arm carries **no** cover stream. Corrected in both documents to state
  the below-chance offset is an **unexplained pooled-correlator artifact** on the as-instrumented
  no-pad traffic, explicitly *not* a padding effect. **No number changed** — this was a prose
  mechanism claim only; the point estimate, CI, gate decision, and Holm outcome are untouched.

## Residual honest limitations (carried, not defects)

- RQ2-P3 funnelling is untestable as-instrumented (zero-variance concentration covariate); the
  *mechanism* behind the RQ2-P1 shrinkage is therefore not empirically resolved, only its
  magnitude. Disclosed in §5.3 and §7.
- The below-chance RQ1-P1 offset now has **no** claimed mechanism; this is the honest state and is
  reported as such rather than back-filled with a speculative cause.

**Outcome:** paper is internally consistent, number-faithful, spin-free, and blinding-honest after
the one mechanism correction. Ready for operator review.
