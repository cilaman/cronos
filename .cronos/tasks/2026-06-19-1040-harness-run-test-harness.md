---
agent_mode: auto
agent_model: default
claude_session_id: edbeb2e9-9fd2-4219-8c40-c681905e6c68
created_at: '2026-06-19T10:40:27Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-1040-harness-run-test-harness
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: 'Harness run: test harness'
type: task
updated_at: '2026-06-19T10:46:33Z'
waiting_question: null
---

# Brief

Automated harness run triggered via API for harness 'test harness'.

# History

```
2026-06-19T10:42:15Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
I'll look at the task workspace and find the "test harness" to understand what needs to be run.

Let me check the harness run context to understand what this task needs to do.

The harness runs the `tester` agent with prompt "run 1 random test from the test suite". I'll execute that now — picking a random test and running it.

Test passed. Now I'll build and POST the report.

Report posted successfully. 

Tests: 1 passed, 0 failed, 0 errors, 0 skipped | Coverage: 18.78% (filtered) | Exit: 0 [FILTERED: test_open_children_all_archived_returns_empty]

STATUS: DONE
```

```
2026-06-19T10:42:51Z [user]
why the cron trigger of the harness was not invoked?
```

```
2026-06-19T10:43:17Z [agent] run=1 model=claude-sonnet-4-6 mode=auto
Let me look at the harness trigger configuration and the cron loop code to diagnose this.

Found the root cause. The trigger node has `expression: 5s`, but `should_fire()` in `cron.py` only accepts **standard 5-field cron expressions** (e.g. `*/5 * * * *`). When `croniter` tries to parse `"5s"` it throws, the `except` block catches it silently, logs a warning, and returns `False` — so the trigger never fires.

```
expression: 5s        # ← not a valid cron expression
```

The `cron.py` docstring and the validator only accept `"0 * * * *"`-style syntax. A duration like `5s` means nothing to `croniter`. The harness was then triggered manually via the API as a workaround.

**To fix**: change the trigger's expression to a valid cron expression. Since the intent seems to be "run frequently", you'd use something like `* * * * *` (every minute) — there's no cron syntax for "every 5 seconds" because cron's minimum granularity is 1 minute.

If sub-minute scheduling is a real requirement, the cron loop would need to be extended to support a separate duration/interval syntax (e.g. parse `Ns` as "fire every N seconds") — that would be a backend feature addition.
```

```
2026-06-19T10:45:05Z [user]
what is the cron style syntax, write me how to use it
```

```
2026-06-19T10:45:24Z [agent] run=2 model=claude-sonnet-4-6 mode=auto
Here's the cron expression syntax for harness triggers:

**Standard 5-field cron format:** `minute hour day-of-month month day-of-week`

```yaml
# trigger node data examples
data: {}                        # no expression = manual-only (never auto-fires)
data:
  expression: "* * * * *"      # every minute
  expression: "*/5 * * * *"    # every 5 minutes
  expression: "0 9 * * *"      # every day at 09:00
  expression: "0 9 * * 1-5"    # weekdays at 09:00
  expression: "30 8 * * 1"     # every Monday at 08:30
  timezone: "Europe/Prague"    # optional; defaults to UTC
```

**Field positions:**
```
┌─ minute     (0-59)
│ ┌─ hour       (0-23)
│ │ ┌─ day/month  (1-31)
│ │ │ ┌─ month     (1-12)
│ │ │ │ ┌─ day/week   (0-6, 0=Sunday)
* * * * *
```

**Special values:** `*` = any, `*/N` = every N, `-` = range, `,` = list.

**Minimum granularity is 1 minute** — cron has no seconds. For your "test harness" that had `expression: 5s`, the closest valid equivalent is `* * * * *` (fires every minute). The `5s` string is malformed for croniter and causes the trigger to silently skip.
```
