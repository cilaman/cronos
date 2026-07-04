"""delivery_workflow — portable delivery-workflow engine.

Host surface (R10b, 02-package-boundary.md §2.2) — everything a host needs is
exported here:

- ``DeliveryRun`` — the facade (start / resume / outcome / cancel).
- ``Outcome`` / ``outcome_from_state`` — the closed run-outcome taxonomy.
- ``RunEvent`` + concrete events, ``NullHost`` — the host notification grammar.
- ``NodeExecutor`` / ``HostPort`` / ``StateOps`` — the three ports a host
  implements.
- Resume event grammar: ``HumanAnswer`` / ``RetryFailed`` / ``RaiseBudget`` /
  ``Nothing`` (+ ``ResumeError``).
- ``LocalProcessExecutor`` / ``LocalHostPort`` — the reference runtime behind
  the standalone CLI (``python -m delivery_workflow run spec.yaml --workdir .``,
  R10e §2.3).
- ``AGENT_STATUS_VOCAB`` / ``agent_result_from_envelope`` — the closed
  agent-status vocabulary boundary every executor maps through.
- ``load_agent_definition`` / ``return_contract`` / ``upstream_scope_section``
  (+ ``AGENTS_DIR``) — the shared brief-composition helpers every brief
  composer builds from.

``runner.run`` / ``runner.resume`` remain importable (the facade delegates to
them) but are not a supported host surface.
"""
from delivery_workflow.briefs import (  # noqa: F401
    AGENTS_DIR,
    load_agent_definition,
    return_contract,
    upstream_scope_section,
)
from delivery_workflow.delivery_run import DeliveryRun  # noqa: F401
from delivery_workflow.events import (  # noqa: F401
    NodeFinished,
    NodeStarted,
    NullHost,
    RunBlocked,
    RunEscalated,
    RunEvent,
    RunFailed,
    RunStalled,
)
from delivery_workflow.interface import (  # noqa: F401
    HostPort,
    NodeExecutor,
    StateOps,
)
from delivery_workflow.local_executor import (  # noqa: F401
    LocalHostPort,
    LocalProcessExecutor,
)
from delivery_workflow.outcome import Outcome, outcome_from_state  # noqa: F401
from delivery_workflow.results import (  # noqa: F401
    AGENT_STATUS_VOCAB,
    agent_result_from_envelope,
)
from delivery_workflow.runner.resume import (  # noqa: F401
    HumanAnswer,
    Nothing,
    RaiseBudget,
    ResumeError,
    ResumeEvent,
    RetryFailed,
)

__all__ = [
    "DeliveryRun",
    "Outcome",
    "outcome_from_state",
    "RunEvent",
    "NodeStarted",
    "NodeFinished",
    "RunBlocked",
    "RunStalled",
    "RunFailed",
    "RunEscalated",
    "NullHost",
    "NodeExecutor",
    "HostPort",
    "StateOps",
    "HumanAnswer",
    "RetryFailed",
    "RaiseBudget",
    "Nothing",
    "ResumeError",
    "ResumeEvent",
    "LocalProcessExecutor",
    "LocalHostPort",
    "AGENT_STATUS_VOCAB",
    "agent_result_from_envelope",
    "AGENTS_DIR",
    "load_agent_definition",
    "return_contract",
    "upstream_scope_section",
]
