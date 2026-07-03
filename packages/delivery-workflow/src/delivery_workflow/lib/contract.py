"""CC-v1 contract — the canonical artifact schema every pipeline agent obeys.

This module is intentionally **data-only**: it exposes the field lists, section
names, rule names, and constants that the verifier, normalizer, schemas, and
(later) the agent prompts all reference. It performs no validation itself and
references no agents — those are layered on top in sibling modules.

The contract is adapted from Delivery Notes Agent Contract v1.0
(``/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md``). Cronos
deviations are documented in :mod:`CONTRACT.md` §"Cronos deviations" and are
visible here as:

* ``memory_hits`` replaces Delivery Notes' ``kb_hits`` (Cronos has no `.kb/`;
  the equivalent substrate is the per-space memory store).
* ``duration_s`` and ``token_spend`` are **trace-owned**. Agents NEVER write
  them — they are derived from the run trace by the trace_parser.
* Artifact paths live under ``{space}/.cronos/pipeline/{goal_slug}/`` rather
  than ``.ai/pipeline/{slug}/``.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Contract version
# ---------------------------------------------------------------------------

CC_VERSION: Final[str] = "1.0"
"""The CC-v1 contract version string written into every pipeline artifact and
checked by the verifier. Bumped on breaking schema changes; minor additive
changes stay on 1.x."""


# ---------------------------------------------------------------------------
# YAML header — mandatory fields, in canonical order
# ---------------------------------------------------------------------------

HEADER_FIELDS: Final[tuple[str, ...]] = (
    "cc_version",
    "agent",
    "slug",
    "phase",
    "status",
    "confidence",
    "inputs_used",
    "outputs_produced",
    "blockers",
    "next_consumer",
    "metrics",
)
"""Canonical order of YAML header fields. Per-class schemas MAY extend this
list with extra fields (e.g. ``coverage_summary`` for research-class agents),
but MUST NOT omit any of these or reorder the base."""


HEADER_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(HEADER_FIELDS)
"""Set form of :data:`HEADER_FIELDS` for O(1) presence checks in the verifier."""


# ---------------------------------------------------------------------------
# status enum — the only legal values for header['status']
# ---------------------------------------------------------------------------

STATUS_VALUES: Final[tuple[str, ...]] = (
    "done",
    "partial",
    "blocked",
    "failed",
)
"""Allowed values for ``status`` in the YAML header.

* ``done`` — agent finished cleanly; downstream may proceed.
* ``partial`` — agent finished best-effort with caveats listed in
  ``## Assumptions`` and/or ``## Open questions``; blockers MUST be empty
  (otherwise R1 coerces to ``blocked``).
* ``blocked`` — agent halted because a precondition was not met; ``blockers``
  MUST be non-empty.
* ``failed`` — agent halted because something went wrong during execution
  (tool errors, contract violations it caught itself); ``blockers`` MUST be
  non-empty.
"""


# ---------------------------------------------------------------------------
# next_consumer sentinel
# ---------------------------------------------------------------------------

NEXT_CONSUMER_USER_SENTINEL: Final[str] = "user"
"""Value to put in ``next_consumer`` when the downstream consumer is the human
(escalation, end-of-pipeline summaries). Any other value MUST be an agent
name from the pipeline registry."""


# ---------------------------------------------------------------------------
# Metrics ownership — Cronos split
# ---------------------------------------------------------------------------

AGENT_REPORTED_METRICS: Final[tuple[str, ...]] = (
    "tool_calls",
    "files_read",
    "memory_hits",
)
"""Metrics the agent counts and writes into its own artifact header.

* ``tool_calls`` — every tool invocation **including** the final Write of the
  agent's own artifact. No "substantive only" filtering.
* ``files_read`` — count of unique files opened via the Read tool. See
  CONTRACT.md §"Counting files_read" for what is/isn't counted.
* ``memory_hits`` — count of memory_store entries surfaced to the agent (via
  the # Memory Context prompt block) that the agent actually relied on, plus
  any explicit memory lookups it performed. Replaces Delivery Notes'
  ``kb_hits`` because Cronos has no `.kb/` substrate.
"""


TRACE_OWNED_METRICS: Final[tuple[str, ...]] = (
    "duration_s",
    "token_spend",
)
"""Metrics derived from the Cronos run trace by ``trace_parser``. Agents
**MUST NOT** write these into their artifact headers — they are stamped
post-hoc (or computed at read time) from the trace. If an agent-written
artifact contains either of these fields, the verifier flags it as a contract
violation."""


# ---------------------------------------------------------------------------
# Markdown body — required sections in canonical order
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS: Final[tuple[str, ...]] = (
    "Summary",
    "Coverage",
    "Findings",
    "Assumptions",
    "Open questions",
    "Next consumer brief",
)
"""Required H2 sections in the markdown body, in this order.

* ``Summary`` — max 5 sentences, decision-oriented.
* ``Coverage`` — what was searched / inspected and what was excluded.
* ``Findings`` — the substantive output; per-class agents MAY rename this
  section to ``Decisions`` (architect, designer) or ``Top relevance`` (scout)
  but the slot is mandatory. The verifier accepts any of the names in
  :data:`FINDINGS_SECTION_ALIASES`.
* ``Assumptions`` — explicit assumptions with one-line justification each.
* ``Open questions`` — may be empty list but the section MUST exist. Agents
  with ``status ∈ {blocked, failed}`` MAY rename to ``Blockers``; the verifier
  accepts either.
* ``Next consumer brief`` — max 300 words, compressed handoff for the
  downstream agent named in ``next_consumer``.

Per-class schemas MAY require additional sections after ``Next consumer
brief`` but MUST NOT omit any of these or change their order.
"""


FINDINGS_SECTION_ALIASES: Final[tuple[str, ...]] = (
    "Findings",
    "Decisions",
    "Top relevance",
)
"""Acceptable H2 names for the ``Findings`` slot. The verifier requires
exactly one of these to be present in the position of ``Findings`` in
:data:`REQUIRED_SECTIONS`."""


OPEN_QUESTIONS_SECTION_ALIASES: Final[tuple[str, ...]] = (
    "Open questions",
    "Blockers",
)
"""Acceptable H2 names for the ``Open questions`` slot. ``Blockers`` is the
conventional name when ``status ∈ {blocked, failed}``."""


# ---------------------------------------------------------------------------
# Cross-field rules — R1 through R7
# ---------------------------------------------------------------------------

R_RULES: Final[tuple[str, ...]] = (
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
)
"""Names of the cross-field rules the verifier enforces on every artifact.
The human-readable definitions live in CONTRACT.md §"Cross-field rules
R1-R7"; this tuple is the canonical identifier set used by verifier outputs,
normalizer logs, and test fixtures.

Summary (full text in CONTRACT.md):

* **R1** — non-empty ``blockers[]`` requires ``status ∈ {blocked, failed}``.
* **R2** — ``status=done`` requires ``confidence >= 0.7``.
* **R3** — ``confidence`` MUST be in ``[0.0, 1.0]``.
* **R4** — ``metrics.files_read + metrics.memory_hits >= len(inputs_used)``.
* **R5** — ``outputs_produced[0]`` SHOULD match the agent's canonical
  artifact path (the per-class schema decides the canonical form).
* **R6** — ``slug`` in the YAML header MUST equal the slug passed by the
  orchestrator; agents NEVER re-derive.
* **R7** — paths in ``inputs_used`` and ``outputs_produced`` MUST be
  workspace-relative forward-slash strings.
"""


# ---------------------------------------------------------------------------
# Artifact path discipline
# ---------------------------------------------------------------------------

ARTIFACT_PATH_TEMPLATE: Final[str] = (
    "{space}/.cronos/pipeline/{goal_slug}/{phase}-report-{goal_slug}.md"
)
"""Canonical artifact path. ``{space}`` is the absolute space directory;
``{goal_slug}`` is the verbatim slug owned by the orchestrator; ``{phase}``
is the phase identifier from the per-class schema (e.g. ``scout``,
``architect``, ``backend-impl``).

Cronos diverges from Delivery Notes' ``.ai/pipeline/{slug}/`` by living under
the per-space ``.cronos/`` state directory so pipeline artifacts share fate
with the rest of Cronos' on-disk state and are excluded from the repo by the
existing ``.gitignore`` for ``.cronos/``.
"""


# ---------------------------------------------------------------------------
# No-prose-parsing rule
# ---------------------------------------------------------------------------

NO_PROSE_PARSING_RULE: Final[str] = (
    "Orchestrators and downstream agents NEVER parse markdown prose to make "
    "routing or gating decisions. Every decision-relevant fact lives in the "
    "YAML header (or per-class schema extensions). If a routing decision "
    "depends on something not in the header, the contract or schema is "
    "incomplete — escalate, do not prose-parse."
)
"""The single rule from which most others derive. Encoded as a string so it
can be embedded verbatim in agent prompts and verifier error messages."""
