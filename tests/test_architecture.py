"""The domain package never imports Streamlit (docs/ARCHITECTURE.md, rule 1)."""
import ast
from pathlib import Path

EIR_DIR = Path(__file__).resolve().parent.parent / "eir"


def test_eir_never_imports_streamlit():
    offenders = []
    for path in EIR_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(n.split(".")[0] == "streamlit" for n in names):
                offenders.append(path.name)
    assert not offenders
