"""
backend/app/harnesses/interpolate — Variable interpolation for harness prompts.

Public API
----------
interpolate(template, root_vars, upstream_outputs) -> (str, list[str])

Precedence rule
---------------
1. root_vars are substituted FIRST (they form the base scope).
2. upstream_outputs OVERRIDE root_vars on key collision (upstream wins).

This means: if both root_vars and upstream_outputs contain the key "lang",
the upstream_outputs value is used in the final substitution.

Implementation notes
--------------------
We use string.Template.safe_substitute so that placeholders whose keys are
absent from the combined scope survive intact (as ``$name`` or ``${name}``)
rather than raising a KeyError.  The list of unresolved names is computed by
comparing the template's pattern against the final combined scope.
"""

from __future__ import annotations

import re
import string


def interpolate(
    template: str,
    root_vars: dict,
    upstream_outputs: dict,
) -> tuple[str, list[str]]:
    """Interpolate *template* using the merged variable scope.

    Parameters
    ----------
    template:
        A ``string.Template``-style template (``$name`` or ``${name}``
        placeholders).
    root_vars:
        Base substitution scope (typically ``Harness.variables``).
    upstream_outputs:
        Outputs captured from already-executed upstream nodes.
        These override *root_vars* on key collision.

    Returns
    -------
    interpolated_text:
        The result of ``safe_substitute`` over the merged scope.
    unresolved:
        Sorted list of placeholder names that could not be resolved
        (i.e. they were present in the template but absent from both
        scopes).  Empty when all placeholders are satisfied.
    """
    # Build the merged scope: start with root_vars, then overlay upstream_outputs.
    merged: dict = {}
    merged.update(root_vars)
    merged.update(upstream_outputs)

    tmpl = string.Template(template)
    interpolated_text = tmpl.safe_substitute(merged)

    # Identify unresolved placeholders: find every placeholder name in the
    # template and check which ones are missing from the merged scope.
    # string.Template.pattern matches both $name and ${name} forms.
    placeholder_names: list[str] = []
    for match in re.finditer(string.Template.pattern, template):
        # The regex has named groups 'named' (for $name) and 'braced' (for ${name}).
        name = match.group("named") or match.group("braced")
        if name is not None and name not in merged:
            if name not in placeholder_names:
                placeholder_names.append(name)

    return interpolated_text, sorted(placeholder_names)
