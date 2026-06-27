#!/usr/bin/env python3
"""Hermetic dependency scanner fixture for gate tests.

Scans requirements.txt in the current directory for known-vulnerable pinned
versions.  Emits pip-audit-shaped JSON to stdout; exits 1 if findings are
present, 0 if the scan is clean.  Never hits the network or a CVE database.
"""
import json
import sys
from pathlib import Path

VULNERABLE_PINS = {
    "django==2.0.0": {"cve": "CVE-2019-14232", "severity": "high"},
    "requests==2.18.0": {"cve": "CVE-2018-18074", "severity": "high"},
}

findings = []
req_file = Path("requirements.txt")
if req_file.exists():
    for line in req_file.read_text().splitlines():
        pin = line.strip().lower()
        for vuln_pin, info in VULNERABLE_PINS.items():
            if pin == vuln_pin.lower():
                pkg, ver = vuln_pin.split("==", 1)
                findings.append(
                    {
                        "package": pkg,
                        "version": ver,
                        "severity": info["severity"],
                        "cve": info["cve"],
                        "description": f"Vulnerable {pkg}=={ver} ({info['cve']})",
                    }
                )

print(json.dumps(findings))
sys.exit(1 if findings else 0)
