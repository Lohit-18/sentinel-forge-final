"""Allow `python -m sentinelforge ...` as an alternative to the `sentinelforge` command."""

from sentinelforge.cli import main

raise SystemExit(main())
