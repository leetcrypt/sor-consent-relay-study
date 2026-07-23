//! R1 — Seed plumbing for SOR determinism.
//!
//! This module is the single source of stochasticity for the SOR
//! (self-observing-relay) measurement instrument. Every stochastic decision the
//! later items make — path selection (R4), churn schedule and selector choices
//! (R7), padding jitter (R4) — draws from a `SorRng` seeded by one `--sor-seed
//! <u64>`. Given the same seed and the same (deterministic) churn script, the
//! circuit-build sequence is byte-identical across runs, which is exactly the R1
//! acceptance check and instrument-validation gate item 2 (seeded bringup
//! reproducible).
//!
//! Nothing here forwards traffic, opens a socket, or spawns an engine. It is a
//! deterministic bookkeeping primitive; the isolated-engine containment
//! assertions live with the forwarder (R4). The algorithm is fully specified
//! (SplitMix64 + SHA-256 domain mixing + Lemire bounded sampling) so it is
//! stable across compiler/`rand` versions and is mirrored bit-for-bit in
//! `cmd_chat/sor/config.py`.

// R5 — in-band consent handshake + per-hop X25519 sealed credentials. Lives in
// its own module; it consumes this module's determinism only indirectly (a hop
// secret is sealed per recipient) and adds no new source of stochasticity here.
pub mod consent;

use serde::Serialize;
use sha2::{Digest, Sha256};

/// Independent stochastic sub-streams. Each SOR decision domain draws from its
/// own stream so that adding or removing a consumer in one domain never
/// perturbs another domain's sequence (stable determinism under refactor).
// Path drives R1/R4 circuit selection now; Churn/Padding/Selector are consumed
// by R4 padding and R7 churn/selector, and are exercised by the R1 tests.
#[allow(dead_code)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Domain {
    /// Circuit path / hop selection (R4).
    Path,
    /// VM spin/kill churn schedule (R7).
    Churn,
    /// Padding jitter timing (R4 optional padding arm).
    Padding,
    /// Agent/path selector strategy choices (R7).
    Selector,
}

impl Domain {
    /// Stable label mixed into the sub-stream seed. Never reorder or rename
    /// these — the bytes are part of the reproducibility contract.
    fn label(self) -> &'static [u8] {
        match self {
            Domain::Path => b"path",
            Domain::Churn => b"churn",
            Domain::Padding => b"padding",
            Domain::Selector => b"selector",
        }
    }
}

/// A deterministic SplitMix64 stream. Fully specified so two runs (or the Rust
/// and Python sides) agree exactly given the same 64-bit state.
#[derive(Clone, Debug)]
pub struct Stream {
    state: u64,
}

impl Stream {
    /// Raw SplitMix64 step (Vigna). All arithmetic wraps mod 2^64.
    pub fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Unbiased integer in `[0, n)` via Lemire's multiply-high with rejection.
    /// Deterministic and bias-free; identical to the Python mirror. `n == 0`
    /// yields 0 (empty range is a caller bug, but must not panic).
    pub fn next_below(&mut self, n: u64) -> u64 {
        if n == 0 {
            return 0;
        }
        let mut x = self.next_u64();
        let mut m = (x as u128) * (n as u128);
        let mut l = m as u64; // low 64 bits
        if l < n {
            // t = (2^64 - n) mod n = (-n) mod n
            let t = n.wrapping_neg() % n;
            while l < t {
                x = self.next_u64();
                m = (x as u128) * (n as u128);
                l = m as u64;
            }
        }
        (m >> 64) as u64
    }
}

/// Root RNG for a run. Holds the master seed and hands out independent,
/// domain-separated deterministic streams.
#[derive(Clone, Copy, Debug)]
pub struct SorRng {
    seed: u64,
}

impl SorRng {
    pub fn new(seed: u64) -> Self {
        SorRng { seed }
    }

    // Read by the R2 manifest writer to echo the seed into manifest.json.
    #[allow(dead_code)]
    pub fn seed(&self) -> u64 {
        self.seed
    }

    /// Derive a domain sub-stream: `state = LE64(SHA256("sor-v1" || label ||
    /// LE64(seed))[..8])`. SHA-256 domain mixing decorrelates the streams so one
    /// domain's draws can't be predicted from another's.
    pub fn stream(&self, domain: Domain) -> Stream {
        let mut h = Sha256::new();
        h.update(b"sor-v1");
        h.update(domain.label());
        h.update(self.seed.to_le_bytes());
        let d = h.finalize();
        let mut b = [0u8; 8];
        b.copy_from_slice(&d[..8]);
        Stream {
            state: u64::from_le_bytes(b),
        }
    }
}

/// Deterministically choose an ordered list of `hops` distinct node indices from
/// a candidate pool of size `pool` using the `Path` stream. This is the
/// "circuit-build sequence" the R1 acceptance check compares across runs.
///
/// Partial Fisher–Yates: stable, unbiased, and reproducible. If `hops >= pool`
/// the whole pool is returned as a deterministic permutation.
// Consumed by the R4 forwarder to lay out circuit hops; exercised now by the R1
// determinism/parity tests.
#[allow(dead_code)]
pub fn select_path(rng: &SorRng, pool: usize, hops: usize) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..pool).collect();
    if pool == 0 {
        return idx;
    }
    let take = hops.min(pool);
    let mut s = rng.stream(Domain::Path);
    for i in 0..take {
        let j = i + s.next_below((pool - i) as u64) as usize;
        idx.swap(i, j);
    }
    idx.truncate(take);
    idx
}

/// A seeded bringup plan: the ordered per-rebuild circuit-build sequence. This
/// is what the `sor-bringup` CLI emits and what R2's manifest writer will echo.
/// Each rebuild draws the *next* path from the same Path stream, so a scripted
/// sequence of rebuilds is reproducible end-to-end from the seed alone.
#[derive(Debug, Serialize)]
pub struct Bringup {
    pub sor_seed: u64,
    pub pool: usize,
    pub hops: usize,
    pub circuits: Vec<Vec<usize>>,
}

/// Build `rebuilds` successive circuits from one seed, advancing a single Path
/// stream across rebuilds (models R7 selector rebuilding dropped circuits).
pub fn bringup(seed: u64, pool: usize, hops: usize, rebuilds: usize) -> Bringup {
    let rng = SorRng::new(seed);
    let take = hops.min(pool);
    let mut s = rng.stream(Domain::Path);
    let mut circuits = Vec::with_capacity(rebuilds);
    for _ in 0..rebuilds {
        // Fresh partial Fisher–Yates over a fresh index vector each rebuild, but
        // drawing from the *continuing* stream so successive rebuilds differ.
        let mut idx: Vec<usize> = (0..pool).collect();
        for i in 0..take {
            let j = i + s.next_below((pool - i) as u64) as usize;
            idx.swap(i, j);
        }
        idx.truncate(take);
        circuits.push(idx);
    }
    Bringup {
        sor_seed: seed,
        pool,
        hops,
        circuits,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Lock the core primitive: canonical SplitMix64 with initial state 0 emits
    // the widely published first output. Guards against algorithm drift and
    // keeps the Rust/Python mirrors honest.
    #[test]
    fn splitmix64_known_answer() {
        let mut s = Stream { state: 0 };
        assert_eq!(s.next_u64(), 0xE220_A839_7B1D_CDAF);
        assert_eq!(s.next_u64(), 0x6E78_9E6A_A1B9_65F4);
        assert_eq!(s.next_u64(), 0x06C4_5D18_8009_454F);
    }

    // R1 acceptance check, primitive form: same seed => identical circuit-build
    // sequence; a scripted rebuild sequence is reproducible.
    #[test]
    fn same_seed_identical_bringup() {
        let a = bringup(0xDEADBEEF, 8, 3, 5);
        let b = bringup(0xDEADBEEF, 8, 3, 5);
        assert_eq!(a.circuits, b.circuits);
    }

    // Different seeds diverge (with overwhelming probability for these values).
    #[test]
    fn different_seed_diverges() {
        let a = bringup(1, 12, 3, 4);
        let b = bringup(2, 12, 3, 4);
        assert_ne!(a.circuits, b.circuits);
    }

    // Domain separation: independent streams do not coincide.
    #[test]
    fn domains_decorrelated() {
        let rng = SorRng::new(42);
        let mut p = rng.stream(Domain::Path);
        let mut c = rng.stream(Domain::Churn);
        assert_ne!(p.next_u64(), c.next_u64());
    }

    // select_path returns `hops` distinct in-range indices.
    #[test]
    fn select_path_distinct_in_range() {
        let rng = SorRng::new(7);
        let path = select_path(&rng, 6, 3);
        assert_eq!(path.len(), 3);
        for &h in &path {
            assert!(h < 6);
        }
        let mut sorted = path.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), path.len(), "hops must be distinct");
    }

    // Cross-language parity anchor: this exact value is asserted identically in
    // the Python mirror (tests/test_sor_config.py). If either side changes the
    // algorithm, one of the two tests fails.
    #[test]
    fn parity_vector() {
        assert_eq!(select_path(&SorRng::new(42), 8, 3), vec![5, 0, 6]);
        let bp = bringup(123456789, 5, 3, 3);
        assert_eq!(
            bp.circuits,
            vec![vec![4, 1, 3], vec![3, 2, 0], vec![3, 0, 4]]
        );
    }

    proptest! {
        // next_below must stay in range and never panic for any bound, mirroring
        // the parser proptest discipline in net.rs.
        #[test]
        fn next_below_in_range(seed in any::<u64>(), n in 1u64..1_000_000) {
            let rng = SorRng::new(seed);
            let mut s = rng.stream(Domain::Churn);
            for _ in 0..64 {
                prop_assert!(s.next_below(n) < n);
            }
        }

        // select_path never panics and always yields distinct in-range indices
        // for any pool/hops, including degenerate hops >= pool.
        #[test]
        fn select_path_never_panics(seed in any::<u64>(), pool in 0usize..64, hops in 0usize..64) {
            let rng = SorRng::new(seed);
            let path = select_path(&rng, pool, hops);
            prop_assert!(path.len() == hops.min(pool));
            for &h in &path {
                prop_assert!(h < pool);
            }
            let mut sorted = path.clone();
            sorted.sort_unstable();
            sorted.dedup();
            prop_assert_eq!(sorted.len(), path.len());
        }
    }
}
