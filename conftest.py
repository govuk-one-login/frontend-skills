"""Root pytest configuration.

Ensures the repository root is on ``sys.path`` so both the eval suites and the
``scripts/`` unit tests can import the ``evals`` package regardless of the
directory pytest is invoked from.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
