import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import eir/ and ui/ from the repo root
os.environ.setdefault("EIR_STORAGE", "memory")  # tests never touch the demo data on disk
