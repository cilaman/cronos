#!/usr/bin/env python3
"""Hermetic secrets scanner fixture for gate tests.

Scans .py files in the current directory for the PLANTED-SECRET-FOR-GATE-TEST
sentinel string.  Emits gitleaks-shaped JSON to stdout; exits 1 if any findings
are present, 0 if the scan is clean.  Never touches the network.
"""
import json
import sys
from pathlib import Path

SENTINEL = "PLANTED-SECRET-FOR-GATE-TEST"

findings = []
for f in sorted(Path(".").rglob("*.py")):
    if f.name == "fake_secrets_scanner.py":
        continue
    try:
        text = f.read_text(errors="ignore")
    except OSError:
        continue
    for lineno, line in enumerate(text.splitlines(), 1):
        if SENTINEL in line:
            findings.append(
                {
                    "RuleID": "planted-test-secret",
                    "severity": "high",
                    "Description": f"Planted secret sentinel in {f}:{lineno}",
                    "Match": line.strip(),
                }
            )

print(json.dumps(findings))
sys.exit(1 if findings else 0)
