"""Building blocks for synthetic events.

Every generated event goes through ``LabEventFactory`` so all events share the
same conventions: UTC timestamps, a unique ``source_event_id`` (so fingerprint
de-duplication never merges two genuine events), and the dataset/scenario labels
used later to evaluate detections.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sentinelforge.inventory import Asset, Identity, Inventory

# Internet source range for perimeter noise (RFC 5737 documentation range, never
# a real host). Used only for blocked inbound probes and random VPN login guesses
# that any internet-facing service sees every day.
SCANNER_PREFIX = "198.51.100."


def iso(when: datetime) -> str:
    return when.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class LabEventFactory:
    inventory: Inventory
    rng: random.Random
    dataset_id: str
    seed: int
    _counter: int = 0

    # --- identity / asset helpers --------------------------------------------
    def identity(self, user: str) -> Identity:
        return self.inventory.identities_by_user[user]

    def asset(self, host: str) -> Asset:
        return self.inventory.assets_by_host[host]

    def workstation_of(self, user: str) -> Asset:
        host = self.identity(user).workstation
        if host is None:
            raise ValueError(f"{user} has no workstation")
        return self.asset(host)

    def ip_of(self, host: str) -> str:
        return str(self.asset(host).ip)

    def home_ip(self, user: str) -> str:
        """A stable carrier-grade NAT address standing in for a home connection."""
        index = [i.user for i in self.inventory.identities].index(user)
        return f"100.64.{10 + index}.{20 + index}"

    def attacker_ip(self) -> str:
        return f"{SCANNER_PREFIX}{self.rng.randint(40, 250)}"

    def ephemeral_port(self) -> int:
        return self.rng.randint(49152, 65535)

    # --- event construction --------------------------------------------------
    def _next_id(self) -> str:
        self._counter += 1
        return f"sfgen-{self.seed}-{self._counter:07d}"

    def make(
        self,
        when: datetime,
        *,
        category: str,
        action: str,
        source_type: str,
        source_host: str,
        scenario_id: str,
        **fields: Any,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "event_time": iso(when),
            "category": category,
            "action": action,
            "source_type": source_type,
            "source_host": source_host,
            "source_event_id": self._next_id(),
            "dataset_id": self.dataset_id,
            "scenario_id": scenario_id,
        }
        event.update({key: value for key, value in fields.items() if value is not None})
        return event

    def auth(
        self,
        when,
        *,
        user,
        host,
        src_ip,
        outcome,
        scenario_id,
        action="logon",
        source_type="synthetic_auth",
        severity=None,
    ) -> dict[str, Any]:
        return self.make(
            when,
            category="authentication",
            action=action,
            source_type=source_type,
            source_host=host,
            scenario_id=scenario_id,
            user=user,
            src_ip=src_ip,
            outcome=outcome,
            severity=severity,
        )

    def process(
        self, when, *, host, user, name, path, parent, scenario_id, command_line=None, sha256=None
    ) -> dict[str, Any]:
        return self.make(
            when,
            category="endpoint",
            action="process_start",
            source_type="synthetic_edr",
            source_host=host,
            scenario_id=scenario_id,
            user=user,
            process_name=name,
            process_path=path,
            parent_process_name=parent,
            process_command_line=command_line,
            file_sha256=sha256,
            outcome="success",
        )

    def connection(
        self, when, *, host, user, dst_ip, dst_port, scenario_id, domain=None, outcome="success"
    ) -> dict[str, Any]:
        return self.make(
            when,
            category="network",
            action="connection",
            source_type="synthetic_edr_network",
            source_host=host,
            scenario_id=scenario_id,
            user=user,
            src_ip=self.ip_of(host),
            src_port=self.ephemeral_port(),
            dst_ip=dst_ip,
            dst_port=dst_port,
            dst_domain=domain,
            outcome=outcome,
        )

    def blocked_inbound(self, when, *, src_ip, dst_ip, dst_port, scenario_id) -> dict[str, Any]:
        return self.make(
            when,
            category="network",
            action="connection_blocked",
            source_type="synthetic_firewall",
            source_host="fw-edge-01",
            scenario_id=scenario_id,
            src_ip=src_ip,
            src_port=self.ephemeral_port(),
            dst_ip=dst_ip,
            dst_port=dst_port,
            outcome="failure",
        )

    def system(
        self,
        when,
        *,
        host,
        action,
        scenario_id,
        user=None,
        target_user=None,
        object_name=None,
        severity=None,
        outcome="success",
        source_type="synthetic_system",
    ) -> dict[str, Any]:
        return self.make(
            when,
            category="system",
            action=action,
            source_type=source_type,
            source_host=host,
            scenario_id=scenario_id,
            user=user,
            target_user=target_user,
            object_name=object_name,
            severity=severity,
            outcome=outcome,
        )

    def app(
        self, when, *, action, user, src_ip, outcome, scenario_id, path="/login", severity=None
    ) -> dict[str, Any]:
        return self.make(
            when,
            category="application",
            action=action,
            source_type="synthetic_webapp",
            source_host="app-portal-01",
            scenario_id=scenario_id,
            user=user,
            src_ip=src_ip,
            object_name=path,
            outcome=outcome,
            severity=severity,
        )
