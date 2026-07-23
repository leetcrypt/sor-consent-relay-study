"""Grid inventory + containment pin for the RQ1+RQ2 confirmatory battery.

Pins the node-role → device mapping for the lab grid (2 phones + laptop) and
probes, at call time, which devices are SSH-reachable and which can host an
**isolated engine** (docker). Writes an auditable ``device-map.json``.

Containment note (load-bearing): every SOR forwarder/hop runs inside an isolated
engine (docker container), never on a phone or the host directly. The physical
phones are *distribution* options for where those isolated containers live; the
operator-blessed fallback for the confirmatory RQ1/RQ2 path is isolated docker
containers co-located on the docker host (as used for gate item 1). So the grid
being partly degraded does not by itself collapse the topology — but any inability
to honour the §2 topology / §6 matched-N with isolated nodes is a STOP-and-flag.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Device:
    """A pinned grid device and the house-role it plays in the confirmatory design."""

    name: str            # ssh alias / stable id
    kind: str            # "phone" | "laptop"
    arch: str            # "aarch64" | "x86_64"
    can_host_engine: bool  # can run an isolated docker engine locally?
    house_role: str      # design role (e.g. "house-A host / hop pool")


# Pinned inventory (lab-only, all ours — CLAUDE.md §Containment). tril + fp6 are
# the two phones; laptop is the x86_64 docker host. Only devices that can host an
# isolated docker engine may run a forwarder; phones without docker are consent
# endpoints / distribution targets, never a bare host forwarder.
GRID_INVENTORY: List[Device] = [
    Device("laptop", "laptop", "x86_64", True, "house-A docker host + hop pool"),
    Device("fp6", "phone", "aarch64", False, "house-B consenting node (phone)"),
    Device("tril", "phone", "aarch64", False, "house-C consenting node (Termux, no docker)"),
]


def _probe_ssh(alias: str, timeout: int = 8) -> bool:
    """Best-effort SSH reachability probe (BatchMode, short timeout). Never raises."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             "-o", "StrictHostKeyChecking=accept-new", alias, "true"],
            capture_output=True, timeout=timeout,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _probe_remote_docker(alias: str, timeout: int = 12) -> bool:
    """Best-effort probe of an isolated docker engine on a remote device. Never raises."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             "-o", "StrictHostKeyChecking=accept-new", alias,
             "docker version --format '{{.Server.Version}}'"],
            capture_output=True, timeout=timeout,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return False


def _probe_local_docker() -> Optional[str]:
    """Local docker server version if a daemon is up, else None. Never raises."""
    if shutil.which("docker") is None:
        return None
    try:
        r = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                           capture_output=True, timeout=12)
        return r.stdout.decode().strip() if r.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def probe_grid() -> Dict[str, Any]:
    """Probe reachability + isolated-engine availability across the pinned grid.
    Pure I/O, no traffic, no forwarder — a connectivity/capability snapshot only."""
    local_docker = _probe_local_docker()
    devices: List[Dict[str, Any]] = []
    for d in GRID_INVENTORY:
        reachable = _probe_ssh(d.name)
        # An isolated engine is available on this device if it is the local docker
        # host (laptop here) or a reachable device advertising a docker daemon.
        if d.name == "laptop":
            engine_ok = local_docker is not None
            engine_ver = local_docker
        elif reachable and d.can_host_engine:
            engine_ok = _probe_remote_docker(d.name)
            engine_ver = "remote-docker" if engine_ok else None
        else:
            engine_ok = False
            engine_ver = None
        devices.append({
            **asdict(d),
            "ssh_reachable": reachable,
            "isolated_engine_available": engine_ok,
            "engine_version": engine_ver,
        })
    return {"local_docker_version": local_docker, "devices": devices}


def write_device_map(out_dir: Path) -> Dict[str, Any]:
    """Write ``device-map.json`` (write-once) pinning the node-role→device map and
    the current reachability/engine snapshot, plus a containment + matched-N
    assessment. Returns the document."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snap = probe_grid()

    engine_hosts = [d for d in snap["devices"] if d["isolated_engine_available"]]
    reachable = [d for d in snap["devices"] if d["ssh_reachable"]]
    down = [d["name"] for d in snap["devices"] if not d["ssh_reachable"]]
    # RQ1/RQ2 hops run as isolated docker containers; a single docker host can
    # host >=3 distinct containerised nodes (operator-blessed, gate item 1). So
    # the topology/matched-N is honourable iff at least one isolated engine exists.
    topology_honourable = len(engine_hosts) >= 1

    doc = {
        "schema": "sor-device-map/1",
        "scope": "RQ1+RQ2 lead-paper grid pin (CLAUDE.md §Containment)",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local_docker_version": snap["local_docker_version"],
        "devices": snap["devices"],
        "reachable_count": len(reachable),
        "isolated_engine_host_count": len(engine_hosts),
        "degraded": bool(down),
        "devices_down": down,
        "topology_matchedN_honourable": topology_honourable,
        "containment": {
            "hops_run_in": "isolated docker containers only (never a phone/host forwarder)",
            "external_target": "none",
            "live_vm_churn_on_rq1_rq2": "none (RQ1/RQ2 use no churn; churn_schedule_id=none)",
            "self_traffic_only": True,
        },
        "matched_N_note": (
            "RQ1/RQ2 isolated hops are containerised on the docker host (>=3 distinct "
            "containers = distinct nodes). Physical-phone distribution is optional; the "
            "confirmatory matched-N (single-house N = federated total consenting nodes) is "
            "pinned from the containerised node count at run time and recorded per manifest."
        ),
        "assessment": (
            "GO on isolated docker host" if topology_honourable
            else "STOP: no isolated engine available — topology/matched-N cannot be honoured"
        ),
    }
    path = out_dir / "device-map.json"
    if not path.exists():
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc["_report_path"] = str(path)
    return doc
