"""The lab's synthetic asset and identity inventory (configs/lab_inventory.yml).

A real SOC knows which machines matter most and which accounts are
privileged. That context turns "a failed login" into "a failed login against
the domain administrator account". The inventory provides it.
"""

from __future__ import annotations

import ipaddress
from functools import cached_property
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, field_validator

AssetRole = Literal[
    "workstation", "server", "domain_controller", "vpn_gateway", "web_app", "firewall"
]
Criticality = Literal["low", "medium", "high", "critical"]

# Hosts with these roles are shared by many users (everyone logs in through the
# VPN gateway, every connection crosses the firewall). They are not used to link
# unrelated activity together during correlation.
SHARED_INFRASTRUCTURE_ROLES = frozenset({"vpn_gateway", "web_app", "firewall"})


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user: str
    department: str
    workstation: str | None = None
    privileged: bool = False
    service: bool = False
    remote: bool = False


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str
    role: AssetRole
    ip: IPvAnyAddress
    owner: str | None = None
    criticality: Criticality = "medium"


class KnownDestination(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: str
    ip: IPvAnyAddress
    port: int = Field(ge=1, le=65535)
    purpose: str


class BusinessHours(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int = Field(ge=0, le=23)
    end: int = Field(ge=1, le=24)


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organisation: str
    business_hours_utc: BusinessHours
    internal_networks: list[str]
    privileged_groups: list[str]
    authorised_admins: list[str]
    identities: list[Identity]
    assets: list[Asset]
    known_destinations: list[KnownDestination] = []

    @field_validator("internal_networks")
    @classmethod
    def _valid_networks(cls, value: list[str]) -> list[str]:
        for network in value:
            ipaddress.ip_network(network)
        return value

    # --- lookups -----------------------------------------------------------
    @cached_property
    def identities_by_user(self) -> dict[str, Identity]:
        return {identity.user: identity for identity in self.identities}

    @cached_property
    def assets_by_host(self) -> dict[str, Asset]:
        return {asset.host: asset for asset in self.assets}

    @cached_property
    def assets_by_ip(self) -> dict[str, Asset]:
        return {str(asset.ip): asset for asset in self.assets}

    @cached_property
    def _internal(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [ipaddress.ip_network(n) for n in self.internal_networks]

    @cached_property
    def known_destination_ips(self) -> frozenset[str]:
        return frozenset(str(d.ip) for d in self.known_destinations)

    @cached_property
    def known_destination_domains(self) -> frozenset[str]:
        return frozenset(d.domain for d in self.known_destinations)

    def is_internal(self, ip: str | None) -> bool:
        if not ip:
            return False
        address = ipaddress.ip_address(ip)
        return any(address in network for network in self._internal)

    def is_privileged(self, user: str | None) -> bool:
        identity = self.identities_by_user.get(user or "")
        return bool(identity and identity.privileged)

    def criticality(self, host: str | None) -> str:
        asset = self.assets_by_host.get(host or "")
        return asset.criticality if asset else "medium"

    def is_shared_infrastructure(self, host: str | None) -> bool:
        asset = self.assets_by_host.get(host or "")
        return bool(asset and asset.role in SHARED_INFRASTRUCTURE_ROLES)

    def is_business_hour(self, hour: int) -> bool:
        return self.business_hours_utc.start <= hour < self.business_hours_utc.end


def load_inventory(path: Path) -> Inventory:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)  # safe_load never executes code from the file
    return Inventory.model_validate(data)
