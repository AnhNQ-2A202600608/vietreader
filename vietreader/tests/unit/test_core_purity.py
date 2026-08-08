"""Architectural guardrail: vietreader.core must never import I/O-capable modules.

Enforces the rule in AGENT_WORK_ORDER_VietReader.md §1.2: modules in core/ must not import
anything from db/, api/, llm/, extraction/, or httpx/sqlalchemy/fastapi.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "vietreader" / "core"

FORBIDDEN_MODULES = {
    "vietreader.db",
    "vietreader.api",
    "vietreader.llm",
    "vietreader.extraction",
    "httpx",
    "sqlalchemy",
    "fastapi",
}


def _forbidden_hit(module_name: str) -> str | None:
    for forbidden in FORBIDDEN_MODULES:
        if module_name == forbidden or module_name.startswith(forbidden + "."):
            return forbidden
    return None


def _imports_in_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _core_files() -> list[Path]:
    return sorted(CORE_DIR.glob("*.py"))


@pytest.mark.parametrize("path", _core_files(), ids=lambda p: p.name)
def test_core_module_has_no_forbidden_imports(path: Path) -> None:
    violations = [
        (module, hit)
        for module in _imports_in_file(path)
        if (hit := _forbidden_hit(module)) is not None
    ]
    assert violations == [], f"{path.name} imports forbidden modules: {violations}"


def test_core_dir_is_non_empty_so_this_test_cannot_pass_vacuously() -> None:
    assert len(_core_files()) >= 5
