# TEST FIXTURE — deliberately contains forbidden app.* imports to verify the boundary checker detects them.
# This file must NEVER be imported by package code; it exists solely as a detection test fixture.
from app.storage import TaskStore  # noqa: F401
import app.main  # noqa: F401
