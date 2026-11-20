"""Lets research scripts import the backend package (app.*) without installing it."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
RESEARCH = REPO / "research"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
