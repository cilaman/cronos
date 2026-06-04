Implement the three control-flow evaluators in the interpreter. These run
**in-process; never a subprocess, never a child task.**

- **Decision:** branch on the upstream Agent signal — STATUS marker (already in
  `AgentResult.status`), regex on `final_text_snippet`, or harness-variable compare.
  Define precedence + missing-signal behaviour; pick the outgoing edge by `condition` label.
- **Wait:** human (map to `TaskState.WAITING` + resume via the existing reply/`pending_messages`
  mechanism), time (resume after N), or upstream signal.
- **Aggregator:** join N upstreams; emit on **all** or **any** (configurable). Define
  partial-failure semantics.
- Reject/bound Decision-edge cycles in the 6.1 validator; add an unbounded-wait guardrail.

Acceptance: a Decision routes to edge A on `STATUS: DONE`, edge B on `STATUS: BLOCKED`;
Aggregator `all` waits for both, `any` fires first; Wait(human) parks in WAITING and
resumes on reply.

