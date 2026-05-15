---
claude_session_id: 2c0f4b2e-7a91-4b1a-93d5-1234567890ab
created_at: '2026-05-14T15:30:00Z'
id: 2026-05-14-1530-refactor-notifications
state: backlog
title: Extract notifications module into its own package
updated_at: '2026-05-15T10:19:13Z'
waiting_question: null
---

# Brief

The notifications code is currently tangled into the user-service. Pull
the publisher, subscriber, and templates into a standalone package under
`packages/notifications/`. Keep the public API stable so callers don't
need to change beyond updating their import paths.

# History

```
2026-05-14T18:12:00Z [agent]
Moved publisher.py, subscriber.py, templates/ into packages/notifications/.
Updated 14 import sites across user-service. All tests pass.
Next step: verify the package builds as a wheel and update the monorepo build config.
```
