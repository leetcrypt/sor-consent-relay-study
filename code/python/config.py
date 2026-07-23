"""R1 — Seed plumbing for SOR determinism (Python mirror of hh/src/sor/mod.rs).

The SOR instrument's stochastic decisions — path selection (R4), churn schedule
and selector choices (R7), padding jitter (R4) — draw from a single
``--sor-seed <u64>``. Given the same seed and the same (deterministic) churn
script the circuit-build sequence is byte-identical across runs, which is the
R1 acceptance check and instrument-validation gate item 2.

Nothing here forwards traffic or spawns an engine; it is a deterministic
bookkeeping primitive. The isolated-engine containment assertions live with the
forwarder (R4). The algorithm — SplitMix64 + SHA-256 domain mixing + Lemire
bounded sampling — is fully specified and matches the Rust core exactly, so a
seed means the same thing on both sides (see tests/test_sor_config.py, which
asserts the same parity vectors as hh/src/sor/mod.rs::tests::parity_vector).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import List

_MASK64 = (1 << 64) - 1


class Domain(Enum):
    """Independent stochastic sub-streams. Each SOR decision domain draws from
    its own stream so adding/removing a consumer in one domain never perturbs
    another. The label bytes are part of the reproducibility contract — never
    reorder or rename."""

    PATH = b"path"
    CHURN = b"churn"
    PADDING = b"padding"
    SELECTOR = b"selector"


class Stream:
    """Deterministic SplitMix64 stream. Identical to the Rust `Stream`."""

    __slots__ = ("_state",)

    def __init__(self, state: int) -> None:
        self._state = state & _MASK64

    def next_u64(self) -> int:
        """Raw SplitMix64 step (Vigna). All arithmetic wraps mod 2^64."""
        self._state = (self._state + 0x9E3779B97F4A7C15) & _MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return z ^ (z >> 31)

    def next_below(self, n: int) -> int:
        """Unbiased integer in [0, n) via Lemire's multiply-high with rejection.
        Matches the Rust mirror. n == 0 yields 0 (must not raise)."""
        if n <= 0:
            return 0
        x = self.next_u64()
        m = x * n
        low = m & _MASK64
        if low < n:
            t = ((_MASK64 + 1) - n) % n  # (2^64 - n) mod n
            while low < t:
                x = self.next_u64()
                m = x * n
                low = m & _MASK64
        return m >> 64


class SorRng:
    """Root RNG: master seed handing out domain-separated deterministic streams."""

    __slots__ = ("_seed",)

    def __init__(self, seed: int) -> None:
        self._seed = seed & _MASK64

    @property
    def seed(self) -> int:
        return self._seed

    def stream(self, domain: Domain) -> Stream:
        """state = LE64(SHA256("sor-v1" || label || LE64(seed))[:8])."""
        h = hashlib.sha256()
        h.update(b"sor-v1")
        h.update(domain.value)
        h.update(self._seed.to_bytes(8, "little"))
        state = int.from_bytes(h.digest()[:8], "little")
        return Stream(state)


def select_path(rng: SorRng, pool: int, hops: int) -> List[int]:
    """Deterministically choose an ordered list of `hops` distinct node indices
    from a candidate pool of size `pool` (partial Fisher-Yates on the Path
    stream). This is the circuit-build sequence the R1 check compares."""
    idx = list(range(pool))
    if pool == 0:
        return idx
    take = min(hops, pool)
    s = rng.stream(Domain.PATH)
    for i in range(take):
        j = i + s.next_below(pool - i)
        idx[i], idx[j] = idx[j], idx[i]
    return idx[:take]


def bringup(seed: int, pool: int, hops: int, rebuilds: int) -> List[List[int]]:
    """Build `rebuilds` successive circuits from one seed, advancing a single
    Path stream across rebuilds (models R7 selector rebuilding dropped
    circuits). Byte-identical to hh/src/sor/mod.rs::bringup."""
    rng = SorRng(seed)
    take = min(hops, pool)
    s = rng.stream(Domain.PATH)
    circuits: List[List[int]] = []
    for _ in range(rebuilds):
        idx = list(range(pool))
        for i in range(take):
            j = i + s.next_below(pool - i)
            idx[i], idx[j] = idx[j], idx[i]
        circuits.append(idx[:take])
    return circuits


@dataclass
class SorConfig:
    """Run configuration carrying the master seed. Later items extend this with
    topology, selector, and churn-schedule ids; R2's manifest writer reads it.
    Kept minimal at R1 to avoid pre-building the later surface."""

    seed: int

    def rng(self) -> SorRng:
        return SorRng(self.seed)
