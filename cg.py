"""Run the Context Guardian CLI directly from a source checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from context_guardian.cli import main

raise SystemExit(main())
