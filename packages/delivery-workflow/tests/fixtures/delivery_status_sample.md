# Sample delivery_status fixture

This file is used by tests/test_delivery_status.py. It contains a verbatim
delivery_status fenced block copied from the scout-report-delivery-v1.md output.

```delivery_status
{
  "status": "done",
  "artifact_paths": [".cronos/pipeline/delivery-v1/scout-report-delivery-v1.md"],
  "produces": "research",
  "fields": {
    "memory_hits": 0,
    "critical_blockers": ["G0.1", "G0.3", "G3.3", "G1.3"],
    "implementation_status": "35-40% complete (contract + verifier done; executor interface, structured-return parsing, adapter missing)",
    "estimated_weeks_to_milestone": 4
  },
  "open_questions": [],
  "telemetry": {
    "tokens": 8240,
    "usd": 0.124,
    "seconds": 34
  }
}
```

The block above is the canonical example from the delivery/v1 scout run.
