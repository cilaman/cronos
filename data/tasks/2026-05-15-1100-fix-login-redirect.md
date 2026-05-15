---
claude_session_id: null
created_at: '2026-05-15T11:00:00Z'
id: 2026-05-15-1100-fix-login-redirect
state: backlog
title: Fix login redirect loop after SSO sign-in
updated_at: '2026-05-15T10:52:55Z'
waiting_question: null
---

# Brief

Users reported that signing in via SSO occasionally results in a redirect
loop between `/login` and `/dashboard`. Reproduces only when the session
cookie's `SameSite` attribute is `Strict` and the user is hitting the app
via a deep link. Investigate, identify the root cause, and propose a fix
that doesn't regress non-deep-link sign-ins.

# History

```
2026-05-15T10:25:43Z [agent]
Not logged in · Please run /login

(exit code 1; stderr tail: )
```

```
2026-05-15T10:26:27Z [agent]
Not logged in · Please run /login

(exit code 1; stderr tail: )
```

```
2026-05-15T10:38:42Z [user]
This is my reply
```

```
2026-05-15T10:38:42Z [agent]
(no assistant text)

(exit code 1; stderr tail: No conversation found with session ID: fa1fc7e2-2ff5-46c9-93e4-81eb0d4b0c46)
```

```
2026-05-15T10:42:29Z [agent]
Not logged in · Please run /login

(exit code 1; stderr tail: )
```
