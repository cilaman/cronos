"""Re-export stub — single canonical source is packages/delivery-workflow/lib/verify.py."""
from lib.verify import (
    CLASS_CONFIG,
    EXIT_PROCEED,
    EXIT_FAIL,
    EXIT_ESCALATE,
    EXIT_RETRY,
    VerifyResult,
    canonical_artifact_relpath,
    verify,
    split_frontmatter,
    PER_CLASS_REQUIRED_SECTIONS,
    main,
    SCHEMAS_DIR,
    load_schema,
    validate_path_format,
)

__all__ = [
    "CLASS_CONFIG",
    "EXIT_PROCEED",
    "EXIT_FAIL",
    "EXIT_ESCALATE",
    "EXIT_RETRY",
    "VerifyResult",
    "canonical_artifact_relpath",
    "verify",
    "split_frontmatter",
    "PER_CLASS_REQUIRED_SECTIONS",
    "main",
    "SCHEMAS_DIR",
    "load_schema",
    "validate_path_format",
]

if __name__ == "__main__":
    import sys
    sys.exit(main())
