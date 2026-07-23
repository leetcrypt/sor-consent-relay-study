"""R5 — In-band consent handshake + X25519 hop credentials (Python mirror).

This is the bit-for-bit Python counterpart of ``hh/src/sor/consent.rs`` and the
sealed-box in ``hh/src/crypto.rs``. Recruitment into a SOR circuit is opt-in and
signed: a host broadcasts a signed ``{"_sor":{"op":"request",...}}`` control
frame (invisible to the zero-knowledge server); each node renders accept/reject;
on accept the node returns an ephemeral hop credential **sealed to the host's
X25519 key only**, so no third party — not even another room member or the relay
— can read it. Requests are signed with the Ed25519 persona and verified before
anything is accepted: an unsigned or forged request is rejected and never yields
a circuit entry.

Wire/crypto contract (mirrors the Rust; never change in place):

    epk, esk = ephemeral X25519 keypair (fresh per seal -> forward secrecy)
    shared   = X25519(esk, recipient_pub)
    key      = HKDF-SHA256(ikm=shared, salt=epk||recipient_pub, info=b"sor-hop-cred-v1")[:32]
    token    = Fernet(urlsafe_b64(key)).encrypt(plaintext)
    sealed   = base64(epk) || "." || fernet_token

This module performs no I/O, opens no socket, and stands up no forwarder — those
are R4, gated by the isolated-engine assertion. It only decides *who* may be
recruited and mints the per-hop secret. The frame parser never raises on
arbitrary input (mirrors the never-panic discipline of ``net.rs``/``consent.rs``).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.hashes import SHA256

# Version tag bound into every signed consent message. Part of the wire
# contract; mirrored in consent.rs; never change in place.
CONSENT_CTX = "sor-consent-v1"

# Domain-separation label for the hop-credential KDF. Mirrors crypto.rs SEAL_CTX.
SEAL_CTX = b"sor-hop-cred-v1"


# --------------------------------------------------------------------------- #
# X25519 sealed box — bit-compatible with hh/src/crypto.rs.
# --------------------------------------------------------------------------- #
def _b64e(raw: bytes) -> str:
    return base64.standard_b64encode(raw).decode("ascii")


def _b64d_32(b64: str) -> bytes:
    raw = base64.standard_b64decode(b64)
    if len(raw) != 32:
        raise ValueError("expected 32-byte key")
    return raw


def _seal_key(shared: bytes, epk: bytes, recipient_pub: bytes) -> bytes:
    """HKDF-SHA256(ikm=shared, salt=epk||recipient_pub, info=SEAL_CTX)[:32]."""
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=epk + recipient_pub,
        info=SEAL_CTX,
    ).derive(shared)


def _fernet_from_key(key: bytes) -> Fernet:
    # Rust uses URL_SAFE (padded) base64 of the 32-byte key; match exactly.
    return Fernet(base64.urlsafe_b64encode(key))


def x25519_keypair() -> tuple[str, str]:
    """Fresh X25519 keypair as ``(secret_b64, public_b64)`` in STANDARD base64."""
    sk = X25519PrivateKey.generate()
    sk_raw = sk.private_bytes_raw()
    pk_raw = sk.public_key().public_bytes_raw()
    return _b64e(sk_raw), _b64e(pk_raw)


def seal_to_pubkey(recipient_pub_b64: str, plaintext: bytes) -> str:
    """Seal ``plaintext`` to ``recipient_pub_b64``. Only the holder of the
    matching secret can :func:`open_sealed` the result."""
    recipient_pub = _b64d_32(recipient_pub_b64)
    eph = X25519PrivateKey.generate()
    epk = eph.public_key().public_bytes_raw()
    shared = eph.exchange(X25519PublicKey.from_public_bytes(recipient_pub))
    key = _seal_key(shared, epk, recipient_pub)
    token = _fernet_from_key(key).encrypt(plaintext).decode("ascii")
    return f"{_b64e(epk)}.{token}"


def open_sealed(recipient_secret_b64: str, sealed: str) -> bytes:
    """Open a ``sealed`` blob with ``recipient_secret_b64``. Raises on a wrong
    secret or a tampered token."""
    epk_b64, _, token = sealed.partition(".")
    if not token:
        raise ValueError("malformed sealed blob")
    epk = _b64d_32(epk_b64)
    sk = X25519PrivateKey.from_private_bytes(_b64d_32(recipient_secret_b64))
    recipient_pub = sk.public_key().public_bytes_raw()
    shared = sk.exchange(X25519PublicKey.from_public_bytes(epk))
    key = _seal_key(shared, epk, recipient_pub)
    try:
        return _fernet_from_key(key).decrypt(token.encode("ascii"))
    except InvalidToken as exc:  # wrong key or tampered
        raise ValueError("sealed-box open failed (wrong key or tampered)") from exc


# --------------------------------------------------------------------------- #
# Ed25519 persona sign/verify — mirrors hh/src/persona.rs::{sign,verify}.
# --------------------------------------------------------------------------- #
def persona_verify(pub_b64: str, sig_b64: str, msg: bytes) -> bool:
    """True iff ``sig_b64`` is a valid Ed25519 signature over ``msg`` by the
    persona ``pub_b64``. Never raises — any decode/verify failure is ``False``."""
    try:
        pk = Ed25519PublicKey.from_public_bytes(base64.standard_b64decode(pub_b64))
        pk.verify(base64.standard_b64decode(sig_b64), msg)
        return True
    except (InvalidSignature, ValueError, Exception):  # noqa: BLE001
        return False


def persona_sign(secret_raw: bytes, msg: bytes) -> str:
    """Sign ``msg`` with a raw 32-byte Ed25519 seed; return STANDARD b64 sig."""
    sk = Ed25519PrivateKey.from_private_bytes(secret_raw)
    return _b64e(sk.sign(msg))


# --------------------------------------------------------------------------- #
# Consent protocol — mirrors the structs/decisions in consent.rs.
# --------------------------------------------------------------------------- #
@dataclass
class ConsentRequest:
    host_ed_pub: str
    host_x_pub: str
    circuit_id: str
    hop_index: int
    nonce: str
    sig: str

    def canonical(self) -> bytes:
        """Canonical signed bytes — identical to consent.rs::canonical."""
        return (
            f"{CONSENT_CTX}\nrequest\n{self.host_ed_pub}\n{self.host_x_pub}\n"
            f"{self.circuit_id}\n{self.hop_index}\n{self.nonce}"
        ).encode("utf-8")

    def signature_ok(self) -> bool:
        return persona_verify(self.host_ed_pub, self.sig, self.canonical())


@dataclass
class ConsentAccept:
    node_ed_pub: str
    circuit_id: str
    hop_index: int
    sealed_cred: str


@dataclass
class ConsentReject:
    node_ed_pub: str
    circuit_id: str
    hop_index: int
    reason: str


def node_evaluate(
    req: ConsentRequest,
    node_ed_pub: str,
    willing: bool,
    hop_secret: bytes,
) -> ConsentAccept | ConsentReject:
    """Node side: evaluate a recruitment request. Signature-gated — a request
    whose signature does not verify is rejected outright (no credential minted).
    A verified request, if the node opts in, yields an acceptance carrying a hop
    credential sealed to the host's X25519 key."""
    if not req.signature_ok():
        return ConsentReject(node_ed_pub, req.circuit_id, req.hop_index,
                             "signature verification failed")
    if not willing:
        return ConsentReject(node_ed_pub, req.circuit_id, req.hop_index, "declined")
    try:
        sealed = seal_to_pubkey(req.host_x_pub, hop_secret)
    except (ValueError, Exception):  # noqa: BLE001 — unsealable advertised key
        return ConsentReject(node_ed_pub, req.circuit_id, req.hop_index,
                             "unsealable host key")
    return ConsentAccept(node_ed_pub, req.circuit_id, req.hop_index, sealed)


@dataclass
class Hop:
    node_fp: str
    hop_index: int
    cred: bytes


def _fingerprint_of(pub_b64: str) -> str:
    """sha256(raw pubkey)[:4] hex — mirrors persona.rs::fingerprint_of."""
    import hashlib

    try:
        raw = base64.standard_b64decode(pub_b64)
        return hashlib.sha256(raw).digest()[:4].hex()
    except Exception:  # noqa: BLE001
        return "unknown"


class CircuitBuilder:
    """Host side: assembles a circuit from consent decisions. The host holds the
    X25519 secret matching the pubkey it advertised, so it — and only it — can
    open the sealed credentials."""

    def __init__(self, circuit_id: str, x_secret_b64: str) -> None:
        self.circuit_id = circuit_id
        self._x_secret_b64 = x_secret_b64
        self.hops: List[Hop] = []

    def recruit(self, decision: ConsentAccept | ConsentReject) -> bool:
        """Fold one decision into the circuit. Accept adds exactly one hop (after
        opening the sealed credential); reject adds nothing. A decision for a
        different circuit, or a credential the host cannot open, recruits no hop.
        Returns True iff a hop was recruited."""
        if not isinstance(decision, ConsentAccept):
            return False
        if decision.circuit_id != self.circuit_id:
            return False
        try:
            cred = open_sealed(self._x_secret_b64, decision.sealed_cred)
        except (ValueError, Exception):  # noqa: BLE001
            return False
        self.hops.append(Hop(_fingerprint_of(decision.node_ed_pub),
                             decision.hop_index, cred))
        return True


# --------------------------------------------------------------------------- #
# Wire parser — mirrors consent.rs::parse_sor_frame. Never raises.
# --------------------------------------------------------------------------- #
def parse_sor_frame(text: str) -> Optional[dict]:
    """Parse a decrypted ``{"_sor":...}`` control frame into a small tagged dict
    ``{"kind": ..., ...}`` (or ``None`` if it is not a recognized SOR frame).
    Classifies or rejects; never raises on arbitrary input."""
    try:
        v = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(v, dict):
        return None
    inner = v.get("_sor")
    if not isinstance(inner, dict):
        return None
    op = inner.get("op")
    if not isinstance(op, str):
        return None

    def s(k: str) -> str:
        val = inner.get(k)
        return val if isinstance(val, str) else ""

    def u(k: str) -> int:
        val = inner.get(k)
        return val if isinstance(val, int) and not isinstance(val, bool) else 0

    if op == "request":
        return {"kind": "request", "req": ConsentRequest(
            s("host_ed"), s("host_x"), s("cid"), u("hop"), s("nonce"), s("sig"))}
    if op == "accept":
        return {"kind": "accept", "accept": ConsentAccept(
            s("node_ed"), s("cid"), u("hop"), s("sealed"))}
    if op == "reject":
        return {"kind": "reject", "reject": ConsentReject(
            s("node_ed"), s("cid"), u("hop"), s("reason"))}
    if op == "peer":
        return {"kind": "peer"}
    return {"kind": "other"}
