"""Mechanical boundaries (contract section 4)."""
import ast
import inspect

import pytest

from conftest import ROOT

FORBIDDEN = {"extractor", "worker"}


def test_extract_takes_exactly_one_parameter_text():
    from extractor.extract import extract

    params = list(inspect.signature(extract).parameters.values())
    assert [p.name for p in params] == ["text"]
    assert params[0].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              inspect.Parameter.POSITIONAL_ONLY)
    assert params[0].default is inspect.Parameter.empty


def test_extract_returns_contract_shape():
    from extractor.extract import extract

    out = extract("Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29.")
    assert isinstance(out, dict)
    assert set(out) >= {"filing_type", "matter_id", "filed_date"}


def test_worker_default_extractor_is_extract():
    from extractor.extract import extract
    from worker.checks import run_extraction
    from worker.run import run_once

    assert inspect.signature(run_extraction).parameters["extractor"].default is extract
    assert inspect.signature(run_once).parameters["extractor"].default is extract


def _forbidden_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN:
                    hits.append(f"{path}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0]
            if node.level == 0 and top in FORBIDDEN:
                hits.append(f"{path}:{node.lineno} from {mod} import ...")
            # `from .. import worker` / `from ..extractor import x` escaping app/
            if node.level >= 2 and (top in FORBIDDEN or
                                    (not mod and any(a.name in FORBIDDEN for a in node.names))):
                hits.append(f"{path}:{node.lineno} relative import of {mod or node.names[0].name}")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name in ("import_module", "__import__") and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                        and arg.value.split(".")[0] in FORBIDDEN:
                    hits.append(f"{path}:{node.lineno} dynamic import {arg.value}")
    return hits


def test_app_never_imports_extractor_or_worker():
    app_dir = ROOT / "app"
    if not app_dir.is_dir():
        pytest.skip("app/ not present in this checkout")
    files = sorted(app_dir.rglob("*.py"))
    assert files, "app/ has no Python files"
    hits = [h for f in files for h in _forbidden_imports(f)]
    assert hits == [], "app/ must not import extractor or worker:\n" + "\n".join(hits)


def test_boundary_scanner_catches_violations(tmp_path):
    """Guards the guard: the scanner must flag each forbidden form."""
    samples = {
        "a.py": "import worker\n",
        "b.py": "import extractor.extract as e\n",
        "c.py": "from worker.checks import check\n",
        "d.py": "from extractor import extract\n",
        "e.py": "import importlib\nimportlib.import_module('worker.run')\n",
        "f.py": "from .. import worker\n",
    }
    for name, src in samples.items():
        p = tmp_path / name
        p.write_text(src)
        assert _forbidden_imports(p), f"scanner missed {src!r}"
    ok = tmp_path / "ok.py"
    ok.write_text("import sqlite3\nfrom app.db import connect\nworker_count = 2\n")
    assert _forbidden_imports(ok) == []
