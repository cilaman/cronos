Add the three event Trigger kinds (`backend/app/harnesses/triggers.py`).

- **task-state-change:** emit from the worker finalise/transition path without coupling
  the worker to harnesses (publish an event the harness subsystem subscribes to).
- **webhook:** an external route mapping a payload to a run (document the auth scheme —
  Caddy `_auth` may not apply).
- **file-change:** coexist with `watch_spaces_dir` (main.py:90); reuse its events, don't
  double-watch.
- De-dup/debounce; fan out when multiple harnesses subscribe to one event.

Acceptance: moving a task to DONE fires a subscribed harness; a webhook POST starts its
run; a watched file change triggers its harness; duplicates within the debounce window
fire once.

