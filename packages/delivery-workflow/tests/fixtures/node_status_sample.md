# Sample node_status fixture

This file is used by tests/test_node_status.py. It contains a verbatim
node_status fenced block for testing the canonical envelope parse.

```node_status
{
  "status": "done",
  "artifact_paths": [".cronos/pipeline/sg2-node-status-general-sentinel/scout-report-sg2-node-status-general-sentinel.md"],
  "produces": "research",
  "fields": {
    "memory_hits": 2,
    "critical_blockers": [],
    "scope_files_count": 6
  },
  "open_questions": []
}
```

The block above is the canonical example demonstrating the node_status envelope
for a scout phase node.
