"""SOR (self-observing-relay) measurement instrument — Python side.

R1 lands the deterministic seed core (`config`). Later items add provenance
(R2), the immutable event log (R3), the isolated-engine forwarder (R4),
federation (R6), and churn/selector/analysis (R7). Everything stochastic is
driven by the single ``--sor-seed`` defined here, mirrored bit-for-bit in
``hh/src/sor/mod.rs``.
"""
