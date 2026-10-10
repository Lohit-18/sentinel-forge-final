"""Normal day-to-day activity ("background").

Detection is only meaningful against realistic normal behaviour: logins every
morning, office applications, periodic update checks, nightly backups, internet
scanners hitting the firewall. Baseline-driven rules (endpoint and volume
anomalies) learn what "normal" looks like from these events.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sentinelforge.generator.lab import LabEventFactory

BACKGROUND = "background"

# (process name, path template, parent) per department. {user} is filled in.
_OFFICE = [
    ("outlook.exe", r"C:\Program Files\Microsoft Office\root\Office16\outlook.exe", "explorer.exe"),
    ("winword.exe", r"C:\Program Files\Microsoft Office\root\Office16\winword.exe", "explorer.exe"),
    ("excel.exe", r"C:\Program Files\Microsoft Office\root\Office16\excel.exe", "explorer.exe"),
    ("msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "explorer.exe"),
    (
        "teams.exe",
        r"C:\Users\{user}\AppData\Local\Microsoft\Teams\current\teams.exe",
        "explorer.exe",
    ),
    (
        "onedrive.exe",
        r"C:\Users\{user}\AppData\Local\Microsoft\OneDrive\onedrive.exe",
        "explorer.exe",
    ),
    ("notepad.exe", r"C:\Windows\System32\notepad.exe", "explorer.exe"),
    ("splwow64.exe", r"C:\Windows\splwow64.exe", "winword.exe"),  # printing from Word (benign)
]
_ENGINEERING = _OFFICE[:4] + [
    (
        "code.exe",
        r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\code.exe",
        "explorer.exe",
    ),
    ("python.exe", r"C:\Program Files\Python312\python.exe", "code.exe"),
    ("git.exe", r"C:\Program Files\Git\cmd\git.exe", "code.exe"),
]
_IT = _OFFICE[:4] + [
    (
        "powershell.exe",
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "explorer.exe",
    ),
    ("mmc.exe", r"C:\Windows\System32\mmc.exe", "explorer.exe"),
    ("cmd.exe", r"C:\Windows\System32\cmd.exe", "explorer.exe"),
]
CATALOGUE = {"engineering": _ENGINEERING, "it": _IT}

_APP_PAGES = ["/dashboard", "/reports", "/timesheets", "/expenses", "/directory"]
_SCAN_PORTS = [22, 23, 445, 3389, 8080]


def _when(day: datetime, hour: int, minute: int, second: int = 0) -> datetime:
    return day + timedelta(hours=hour, minutes=minute, seconds=second)


def generate_day(lab: LabEventFactory, day: datetime) -> list[dict[str, Any]]:
    """All background events for one day starting at ``day`` (00:00 UTC)."""
    rng, inv, events = lab.rng, lab.inventory, []
    known = inv.known_destinations
    saas = [d for d in known if d.domain != "updates.example.com"]
    updates = next(d for d in known if d.domain == "updates.example.com")

    for identity in inv.identities:
        if identity.service or identity.workstation is None:
            continue
        user, ws = identity.user, identity.workstation
        ws_ip = lab.ip_of(ws)
        start_hour, end_hour = rng.randint(7, 9), rng.randint(16, 18)
        login = _when(day, start_hour, rng.randint(0, 50), rng.randint(0, 59))

        # Remote workers connect through the VPN first.
        if identity.remote and rng.random() < 0.6:
            events.append(
                lab.auth(
                    login - timedelta(minutes=2),
                    user=user,
                    host="srv-vpn-01",
                    src_ip=lab.home_ip(user),
                    outcome="success",
                    scenario_id=BACKGROUND,
                )
            )
        # Occasional typo: one failed attempt shortly before the successful logon.
        if rng.random() < 0.06:
            events.append(
                lab.auth(
                    login - timedelta(seconds=rng.randint(10, 40)),
                    user=user,
                    host="srv-dc-01",
                    src_ip=ws_ip,
                    outcome="failure",
                    scenario_id=BACKGROUND,
                )
            )
        events.append(
            lab.auth(
                login,
                user=user,
                host="srv-dc-01",
                src_ip=ws_ip,
                outcome="success",
                scenario_id=BACKGROUND,
            )
        )

        catalogue = CATALOGUE.get(identity.department, _OFFICE)
        for hour in range(start_hour, end_hour):
            for _ in range(rng.randint(2, 5)):
                name, path, parent = rng.choice(catalogue)
                events.append(
                    lab.process(
                        _when(day, hour, rng.randint(0, 59), rng.randint(0, 59)),
                        host=ws,
                        user=user,
                        name=name,
                        path=path.format(user=user),
                        parent=parent,
                        scenario_id=BACKGROUND,
                    )
                )
            for _ in range(rng.randint(3, 6)):
                destination = rng.choice(saas)
                events.append(
                    lab.connection(
                        _when(day, hour, rng.randint(0, 59), rng.randint(0, 59)),
                        host=ws,
                        user=user,
                        dst_ip=str(destination.ip),
                        dst_port=destination.port,
                        domain=destination.domain,
                        scenario_id=BACKGROUND,
                    )
                )
            if rng.random() < 0.25:  # file share access
                events.append(
                    lab.connection(
                        _when(day, hour, rng.randint(0, 59)),
                        host=ws,
                        user=user,
                        dst_ip=lab.ip_of("srv-file-01"),
                        dst_port=445,
                        scenario_id=BACKGROUND,
                    )
                )

        # Business web application.
        app_time = _when(day, rng.randint(start_hour, end_hour - 1), rng.randint(0, 59))
        events.append(
            lab.app(
                app_time,
                action="login",
                user=user,
                src_ip=ws_ip,
                outcome="success",
                scenario_id=BACKGROUND,
            )
        )
        for i in range(rng.randint(2, 4)):
            events.append(
                lab.app(
                    app_time + timedelta(minutes=2 + i * 3),
                    action="page_view",
                    user=user,
                    src_ip=ws_ip,
                    outcome="success",
                    path=rng.choice(_APP_PAGES),
                    scenario_id=BACKGROUND,
                )
            )
        if rng.random() < 0.15:  # clicking a link they are not allowed to use
            events.append(
                lab.app(
                    app_time + timedelta(minutes=20),
                    action="access_denied",
                    user=user,
                    src_ip=ws_ip,
                    outcome="failure",
                    path="/admin",
                    scenario_id=BACKGROUND,
                )
            )

    # Every workstation checks for software updates about once an hour, all day.
    for asset in inv.assets:
        if asset.role != "workstation":
            continue
        owner = asset.owner
        offset = rng.randint(0, 59)
        for hour in range(24):
            events.append(
                lab.connection(
                    _when(day, hour, offset, rng.randint(0, 50)),
                    host=asset.host,
                    user=owner,
                    dst_ip=str(updates.ip),
                    dst_port=updates.port,
                    domain=updates.domain,
                    scenario_id=BACKGROUND,
                )
            )

    # Nightly backup job on srv-backup-01.
    backup_start = _when(day, 1, rng.randint(0, 5))
    events.append(
        lab.system(
            backup_start,
            host="srv-backup-01",
            action="service_start",
            user="svc_backup",
            object_name="backup_agent",
            scenario_id=BACKGROUND,
        )
    )
    for i in range(rng.randint(18, 25)):
        tool = rng.choice(
            ["robocopy.exe", "robocopy.exe", "robocopy.exe", "7z.exe", "backup_verify.exe"]
        )
        events.append(
            lab.process(
                backup_start + timedelta(seconds=30 + i * 70),
                host="srv-backup-01",
                user="svc_backup",
                name=tool,
                path=rf"C:\Program Files\LabBackup\{tool}",
                parent="backup_agent.exe",
                scenario_id=BACKGROUND,
            )
        )
        if i % 2 == 0:
            events.append(
                lab.connection(
                    backup_start + timedelta(seconds=40 + i * 70),
                    host="srv-backup-01",
                    user="svc_backup",
                    dst_ip=lab.ip_of("srv-file-01"),
                    dst_port=445,
                    scenario_id=BACKGROUND,
                )
            )
    events.append(
        lab.system(
            backup_start + timedelta(minutes=38),
            host="srv-backup-01",
            action="service_stop",
            user="svc_backup",
            object_name="backup_agent",
            scenario_id=BACKGROUND,
        )
    )

    # Domain controller: group policy refresh every 90 minutes.
    for minutes in range(5, 24 * 60, 90):
        events.append(
            lab.system(
                day + timedelta(minutes=minutes, seconds=rng.randint(0, 59)),
                host="srv-dc-01",
                action="policy_refresh",
                object_name="gpo",
                scenario_id=BACKGROUND,
            )
        )

    # File server housekeeping and the web application's service account.
    for hour in range(24):
        if rng.random() < 0.5:
            events.append(
                lab.process(
                    _when(day, hour, rng.randint(0, 59)),
                    host="srv-file-01",
                    user="system",
                    name="searchindexer.exe",
                    path=r"C:\Windows\System32\searchindexer.exe",
                    parent="services.exe",
                    scenario_id=BACKGROUND,
                )
            )
        events.append(
            lab.app(
                _when(day, hour, rng.randint(0, 59)),
                action="api_call",
                user="svc_web",
                src_ip=lab.ip_of("srv-app-01"),
                outcome="success",
                path="/api/sync",
                scenario_id=BACKGROUND,
            )
        )

    # Internet noise: scanners probing the perimeter, random login guesses on the VPN.
    for _ in range(rng.randint(15, 30)):
        events.append(
            lab.blocked_inbound(
                _when(day, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)),
                src_ip=lab.attacker_ip(),
                dst_ip=rng.choice([lab.ip_of("srv-vpn-01"), lab.ip_of("app-portal-01")]),
                dst_port=rng.choice(_SCAN_PORTS),
                scenario_id=BACKGROUND,
            )
        )
    for _ in range(rng.randint(1, 4)):
        events.append(
            lab.auth(
                _when(day, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)),
                user=rng.choice(["admin", "test", "root", "guest"]),
                host="srv-vpn-01",
                src_ip=lab.attacker_ip(),
                outcome="failure",
                scenario_id=BACKGROUND,
            )
        )

    return events
