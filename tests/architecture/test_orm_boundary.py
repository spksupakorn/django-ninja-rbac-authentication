"""Architecture guardrails for the repository-only ORM boundary."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).parents[2] / "apps"
ORM_METHODS = frozenset({"save", "delete", "refresh_from_db"})
ALLOWED_DIRECTORY_PARTS = frozenset({"repositories", "migrations", "management"})
ALLOWED_FILENAMES = frozenset({"models.py", "repositories.py"})
BOUNDARY_DIRECTORY_PARTS = frozenset({"api", "services"})


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    expression: str


class _OrmTouchpointVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, source: str) -> None:
        self.path = path
        self.source = source
        self.violations: list[Violation] = []
        self._decorator_call_ids: set[int] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._remember_decorator_calls(node.decorator_list)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._remember_decorator_calls(node.decorator_list)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._remember_decorator_calls(node.decorator_list)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "objects":
            self._add(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in ORM_METHODS
            and id(node) not in self._decorator_call_ids
        ):
            self._add(node.func)
        self.generic_visit(node)

    def _remember_decorator_calls(self, decorators: list[ast.expr]) -> None:
        self._decorator_call_ids.update(
            id(child)
            for decorator in decorators
            for child in ast.walk(decorator)
            if isinstance(child, ast.Call)
        )

    def _add(self, node: ast.expr) -> None:
        self.violations.append(
            Violation(
                path=self.path,
                line=node.lineno,
                expression=ast.get_source_segment(self.source, node) or "ORM access",
            )
        )


def _is_allowlisted(path: Path) -> bool:
    return path.name in ALLOWED_FILENAMES or bool(ALLOWED_DIRECTORY_PARTS & set(path.parts))


def _find_orm_touchpoints(path: Path, source: str | None = None) -> list[Violation]:
    source = source if source is not None else path.read_text()
    visitor = _OrmTouchpointVisitor(path, source)
    visitor.visit(ast.parse(source, filename=str(path)))
    return visitor.violations


def _has_django_models_import(path: Path) -> bool:
    tree = ast.parse(path.read_text(), filename=str(path))
    return any(
        isinstance(node, ast.ImportFrom)
        and (
            node.module == "django.db.models"
            or (node.module == "django.db" and any(alias.name == "models" for alias in node.names))
        )
        for node in ast.walk(tree)
    )


def test_orm_access_is_confined_to_allowlisted_layers() -> None:
    """Services and APIs may not issue ORM operations directly."""
    violations = [
        violation
        for path in APP_ROOT.rglob("*.py")
        if not _is_allowlisted(path)
        for violation in _find_orm_touchpoints(path)
    ]

    assert not violations, "\n".join(
        f"{violation.path.relative_to(APP_ROOT.parent)}:{violation.line}: "
        f"{violation.expression}" for violation in violations
    )


def test_orm_access_outside_allowlist_is_detected() -> None:
    """Prove the scanner rejects an ORM access planted in a service module."""
    source = """\
class UserService:
    def broken(self):
        return User.objects.get(id=1)
"""

    violations = _find_orm_touchpoints(Path("apps/accounts/services/broken.py"), source)

    assert len(violations) == 1
    assert violations[0].expression == "User.objects"


def test_decorator_calls_are_not_mistaken_for_orm_deletes() -> None:
    source = """\
@admin_router.delete("/{user_id}")
async def delete_user(user_id: int):
    return user_id
"""

    violations = _find_orm_touchpoints(Path("apps/accounts/api/users.py"), source)

    assert not violations


def test_services_and_apis_do_not_import_django_models() -> None:
    """External package submodules need an AST check beside import-linter contracts."""
    violations = [
        path.relative_to(APP_ROOT.parent)
        for path in APP_ROOT.rglob("*.py")
        if BOUNDARY_DIRECTORY_PARTS & set(path.parts) and _has_django_models_import(path)
    ]

    assert not violations, "\n".join(str(path) for path in violations)
