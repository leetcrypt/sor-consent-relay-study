//! R5 — In-band consent handshake + X25519 hop credentials.
//!
//! Recruitment into a SOR circuit is **opt-in and signed**. A host broadcasts a
//! signed `{"_sor":{"op":"request",...}}` control frame (invisible to the
//! zero-knowledge server); each node renders accept/reject. On accept the node
//! returns an ephemeral hop credential **sealed to the host's X25519 key only**
//! (`crypto::seal_to_pubkey`), so no third party — not even another room member
//! or the relay — can read it. Requests are signed with the Ed25519 persona and
//! verified with `persona::verify` before anything is accepted: an unsigned or
//! forged request is rejected and never yields a circuit entry.
//!
//! This module is the protocol + its wire parser. It performs no I/O, opens no
//! socket, and stands up no forwarder — those are R4, gated by the
//! isolated-engine assertion. Here we only decide *who* may be recruited and
//! mint the per-hop secret; the frame parser inherits the never-panic proptest
//! discipline of `net.rs`.

use crate::crypto;
use crate::persona;
use serde_json::Value;

/// Version tag bound into every signed consent message. Part of the wire
/// contract; never change in place.
const CONSENT_CTX: &str = "sor-consent-v1";

/// A parsed `{"_sor":...}` control frame. `Peer` is carried for R6 federation
/// and is only classified here (not acted upon).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SorFrame {
    Request(ConsentRequest),
    Accept(ConsentAccept),
    Reject(ConsentReject),
    /// R6 house-peer roster exchange — classified, handled later.
    Peer,
    /// A recognized `_sor` frame we don't act on yet.
    Other,
}

/// Host → node recruitment request. Signed by the host's Ed25519 persona over
/// [`ConsentRequest::canonical`]; carries the host's X25519 pubkey so the node
/// can seal a credential the host alone can open.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConsentRequest {
    pub host_ed_pub: String,
    pub host_x_pub: String,
    pub circuit_id: String,
    pub hop_index: u32,
    pub nonce: String,
    pub sig: String,
}

impl ConsentRequest {
    /// Canonical bytes that the host signs and the node verifies. Binding every
    /// field means a signature can't be lifted onto a different circuit/hop or a
    /// different host X25519 key.
    pub fn canonical(&self) -> Vec<u8> {
        format!(
            "{CONSENT_CTX}\nrequest\n{}\n{}\n{}\n{}\n{}",
            self.host_ed_pub, self.host_x_pub, self.circuit_id, self.hop_index, self.nonce
        )
        .into_bytes()
    }

    /// True iff the request carries a valid Ed25519 signature from the persona
    /// it claims. This gates acceptance — an unsigned or forged request is
    /// never honored.
    pub fn signature_ok(&self) -> bool {
        persona::verify(&self.host_ed_pub, &self.sig, &self.canonical())
    }
}

/// Node → host acceptance carrying the sealed hop credential.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConsentAccept {
    pub node_ed_pub: String,
    pub circuit_id: String,
    pub hop_index: u32,
    /// Hop credential sealed to the host's X25519 pubkey (`crypto::seal_to_pubkey`).
    pub sealed_cred: String,
}

/// Node → host rejection. Leaves no circuit entry.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConsentReject {
    pub node_ed_pub: String,
    pub circuit_id: String,
    pub hop_index: u32,
    pub reason: String,
}

/// A node's decision on a recruitment request.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Decision {
    Accept(ConsentAccept),
    Reject(ConsentReject),
}

/// Node side: evaluate a recruitment request. **Signature-gated**: a request
/// whose signature does not verify is rejected outright (no credential minted).
/// A verified request, if the node opts in (`willing`), yields an acceptance
/// carrying a hop credential sealed to the host's X25519 key.
pub fn node_evaluate(
    req: &ConsentRequest,
    node_ed_pub: &str,
    willing: bool,
    hop_secret: &[u8],
) -> Decision {
    if !req.signature_ok() {
        return Decision::Reject(ConsentReject {
            node_ed_pub: node_ed_pub.to_string(),
            circuit_id: req.circuit_id.clone(),
            hop_index: req.hop_index,
            reason: "signature verification failed".to_string(),
        });
    }
    if !willing {
        return Decision::Reject(ConsentReject {
            node_ed_pub: node_ed_pub.to_string(),
            circuit_id: req.circuit_id.clone(),
            hop_index: req.hop_index,
            reason: "declined".to_string(),
        });
    }
    match crypto::seal_to_pubkey(&req.host_x_pub, hop_secret) {
        Ok(sealed_cred) => Decision::Accept(ConsentAccept {
            node_ed_pub: node_ed_pub.to_string(),
            circuit_id: req.circuit_id.clone(),
            hop_index: req.hop_index,
            sealed_cred,
        }),
        // If we cannot seal to the advertised host key, treat as a reject rather
        // than silently dropping — the host learns no hop was recruited.
        Err(_) => Decision::Reject(ConsentReject {
            node_ed_pub: node_ed_pub.to_string(),
            circuit_id: req.circuit_id.clone(),
            hop_index: req.hop_index,
            reason: "unsealable host key".to_string(),
        }),
    }
}

/// One recruited hop in a circuit under construction.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hop {
    pub node_fp: String,
    pub hop_index: u32,
    pub cred: Vec<u8>,
}

/// Host side: assembles a circuit from consent decisions. The host holds the
/// X25519 secret matching the pubkey it advertised, so it — and only it — can
/// open the sealed credentials.
pub struct CircuitBuilder {
    x_secret_b64: String,
    pub circuit_id: String,
    pub hops: Vec<Hop>,
}

impl CircuitBuilder {
    pub fn new(circuit_id: &str, x_secret_b64: &str) -> Self {
        CircuitBuilder {
            x_secret_b64: x_secret_b64.to_string(),
            circuit_id: circuit_id.to_string(),
            hops: Vec::new(),
        }
    }

    /// Fold one decision into the circuit. Returns true iff a hop was recruited.
    /// **Accept adds exactly one hop (after opening the sealed credential);
    /// reject adds nothing.** A decision for a different circuit, or a sealed
    /// credential the host cannot open, recruits no hop.
    pub fn recruit(&mut self, decision: &Decision) -> bool {
        match decision {
            Decision::Reject(_) => false,
            Decision::Accept(acc) => {
                if acc.circuit_id != self.circuit_id {
                    return false;
                }
                match crypto::open_sealed(&self.x_secret_b64, &acc.sealed_cred) {
                    Ok(cred) => {
                        let node_fp = persona::fingerprint_of(&acc.node_ed_pub)
                            .unwrap_or_else(|| "unknown".to_string());
                        self.hops.push(Hop {
                            node_fp,
                            hop_index: acc.hop_index,
                            cred,
                        });
                        true
                    }
                    Err(_) => false,
                }
            }
        }
    }
}

/// Parse a decrypted `{"_sor":...}` control frame. Classifies or rejects; never
/// panics on arbitrary input (proptest-covered). Semantic validation (signature,
/// sealing) is the caller's job via the protocol functions above.
pub fn parse_sor_frame(text: &str) -> Option<SorFrame> {
    let v: Value = serde_json::from_str(text).ok()?;
    let inner = v.get("_sor")?;
    let s = |k: &str| inner.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string();
    let u = |k: &str| inner.get(k).and_then(|x| x.as_u64()).unwrap_or(0) as u32;
    match inner.get("op").and_then(|x| x.as_str())? {
        "request" => Some(SorFrame::Request(ConsentRequest {
            host_ed_pub: s("host_ed"),
            host_x_pub: s("host_x"),
            circuit_id: s("cid"),
            hop_index: u("hop"),
            nonce: s("nonce"),
            sig: s("sig"),
        })),
        "accept" => Some(SorFrame::Accept(ConsentAccept {
            node_ed_pub: s("node_ed"),
            circuit_id: s("cid"),
            hop_index: u("hop"),
            sealed_cred: s("sealed"),
        })),
        "reject" => Some(SorFrame::Reject(ConsentReject {
            node_ed_pub: s("node_ed"),
            circuit_id: s("cid"),
            hop_index: u("hop"),
            reason: s("reason"),
        })),
        "peer" => Some(SorFrame::Peer),
        _ => Some(SorFrame::Other),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine;
    use ed25519_dalek::{Signer, SigningKey};
    use proptest::prelude::*;

    const STD: base64::engine::general_purpose::GeneralPurpose =
        base64::engine::general_purpose::STANDARD;

    // A throwaway Ed25519 signer standing in for a node/host persona.
    fn signer(seed: u8) -> (SigningKey, String) {
        let sk = SigningKey::from_bytes(&[seed; 32]);
        let pub_b64 = STD.encode(sk.verifying_key().to_bytes());
        (sk, pub_b64)
    }

    fn signed_request(host_ed_sk: &SigningKey, host_ed_pub: &str, host_x_pub: &str) -> ConsentRequest {
        let mut req = ConsentRequest {
            host_ed_pub: host_ed_pub.to_string(),
            host_x_pub: host_x_pub.to_string(),
            circuit_id: "c0".to_string(),
            hop_index: 1,
            nonce: "deadbeef".to_string(),
            sig: String::new(),
        };
        req.sig = STD.encode(host_ed_sk.sign(&req.canonical()).to_bytes());
        req
    }

    // Full happy path: signed request -> node accepts with a sealed cred -> the
    // host (and only the host) recruits the hop.
    #[test]
    fn accept_recruits_a_hop_only_for_the_host() {
        let (host_ed_sk, host_ed_pub) = signer(1);
        let (host_x_sk, host_x_pub) = crypto::x25519_keypair();
        let (_node_ed_sk, node_ed_pub) = signer(2);

        let req = signed_request(&host_ed_sk, &host_ed_pub, &host_x_pub);
        assert!(req.signature_ok());

        let decision = node_evaluate(&req, &node_ed_pub, true, b"ephemeral-hop-key");
        assert!(matches!(decision, Decision::Accept(_)));

        // Host with the right X25519 secret recruits the hop.
        let mut cb = CircuitBuilder::new("c0", &host_x_sk);
        assert!(cb.recruit(&decision), "accept must recruit a hop");
        assert_eq!(cb.hops.len(), 1);
        assert_eq!(cb.hops[0].cred, b"ephemeral-hop-key");

        // A different host (wrong X25519 secret) cannot open the cred → no hop.
        let (other_x_sk, _other_x_pub) = crypto::x25519_keypair();
        let mut evil = CircuitBuilder::new("c0", &other_x_sk);
        assert!(!evil.recruit(&decision), "third party must not recruit");
        assert!(evil.hops.is_empty());
    }

    // Signature gate: an unsigned/forged request is rejected and recruits nothing.
    #[test]
    fn forged_or_unsigned_request_is_rejected() {
        let (_host_ed_sk, host_ed_pub) = signer(1);
        let (_host_x_sk, host_x_pub) = crypto::x25519_keypair();
        let (_node_ed_sk, node_ed_pub) = signer(2);

        // Unsigned (empty sig).
        let mut unsigned = ConsentRequest {
            host_ed_pub: host_ed_pub.clone(),
            host_x_pub: host_x_pub.clone(),
            circuit_id: "c0".to_string(),
            hop_index: 1,
            nonce: "n".to_string(),
            sig: String::new(),
        };
        assert!(!unsigned.signature_ok());
        assert!(matches!(
            node_evaluate(&unsigned, &node_ed_pub, true, b"k"),
            Decision::Reject(_)
        ));

        // Forged: signed by the WRONG key but claiming host_ed_pub.
        let (wrong_sk, _wrong_pub) = signer(9);
        unsigned.sig = STD.encode(wrong_sk.sign(&unsigned.canonical()).to_bytes());
        assert!(!unsigned.signature_ok(), "forged signature must not verify");
        assert!(matches!(
            node_evaluate(&unsigned, &node_ed_pub, true, b"k"),
            Decision::Reject(_)
        ));
    }

    // A tampered field (hop_index) breaks the signature (canonical binding).
    #[test]
    fn tampering_a_bound_field_breaks_signature() {
        let (host_ed_sk, host_ed_pub) = signer(1);
        let (_host_x_sk, host_x_pub) = crypto::x25519_keypair();
        let mut req = signed_request(&host_ed_sk, &host_ed_pub, &host_x_pub);
        req.hop_index = 2; // was 1 when signed
        assert!(!req.signature_ok());
    }

    // Reject leaves no circuit entry.
    #[test]
    fn reject_leaves_no_entry() {
        let (host_ed_sk, host_ed_pub) = signer(1);
        let (host_x_sk, host_x_pub) = crypto::x25519_keypair();
        let (_node_ed_sk, node_ed_pub) = signer(2);
        let req = signed_request(&host_ed_sk, &host_ed_pub, &host_x_pub);

        // Node declines a validly-signed request.
        let decision = node_evaluate(&req, &node_ed_pub, false, b"k");
        assert!(matches!(decision, Decision::Reject(_)));
        let mut cb = CircuitBuilder::new("c0", &host_x_sk);
        assert!(!cb.recruit(&decision));
        assert!(cb.hops.is_empty(), "reject must leave no circuit entry");
    }

    // Wire round-trip through the parser.
    #[test]
    fn parse_request_roundtrip() {
        let frame = r#"{"_sor":{"op":"request","host_ed":"E","host_x":"X","cid":"c1","hop":3,"nonce":"nn","sig":"ss"}}"#;
        match parse_sor_frame(frame) {
            Some(SorFrame::Request(r)) => {
                assert_eq!(r.host_ed_pub, "E");
                assert_eq!(r.host_x_pub, "X");
                assert_eq!(r.circuit_id, "c1");
                assert_eq!(r.hop_index, 3);
            }
            other => panic!("expected Request, got {other:?}"),
        }
    }

    proptest! {
        // parse_sor_frame consumes attacker-controlled JSON from a zero-knowledge
        // relay: it must classify or reject, never panic (net.rs discipline).
        #[test]
        fn parse_sor_never_panics(s in ".*") {
            let _ = parse_sor_frame(&s);
        }

        #[test]
        fn parse_sor_structured_never_panics(
            op in "[a-z]{0,10}", a in ".*", hop in any::<i64>()
        ) {
            let frame = serde_json::json!({
                "_sor": {"op": op, "host_ed": a, "host_x": a, "cid": a,
                         "hop": hop, "nonce": a, "sig": a, "node_ed": a,
                         "sealed": a, "reason": a}
            })
            .to_string();
            let _ = parse_sor_frame(&frame);
        }
    }
}
