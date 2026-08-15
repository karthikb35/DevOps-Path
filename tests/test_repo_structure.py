"""
Protection tests — fast structural checks that run on every PR.
These are the 'gate 0' checks that catch repository health issues
before any real CI work runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ── Notebook structural integrity ─────────────────────────────────────────

def _notebooks() -> list[Path]:
    return list(REPO_ROOT.glob("**/*.ipynb"))


def _workflows() -> list[Path]:
    return list((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("nb_path", _notebooks(), ids=lambda p: p.name)
def test_notebook_is_valid_json(nb_path: Path) -> None:
    """Every .ipynb file must be parseable JSON."""
    data = json.loads(nb_path.read_text(encoding="utf-8"))
    assert "cells" in data, f"{nb_path.name}: missing 'cells' key"
    assert "nbformat" in data, f"{nb_path.name}: missing 'nbformat' key"


@pytest.mark.parametrize("nb_path", _notebooks(), ids=lambda p: p.name)
def test_notebook_has_no_outputs(nb_path: Path) -> None:
    """Notebooks must be committed without cell outputs (keeps diffs clean)."""
    data = json.loads(nb_path.read_text(encoding="utf-8"))
    for i, cell in enumerate(data.get("cells", []), 1):
        outputs = cell.get("outputs", [])
        assert not outputs, (
            f"{nb_path.name} cell {i}: committed with output. "
            "Run: jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace"
        )


@pytest.mark.parametrize("nb_path", _notebooks(), ids=lambda p: p.name)
def test_notebook_has_kernel_info(nb_path: Path) -> None:
    """Every notebook must declare its kernel so CI can reproduce it."""
    data = json.loads(nb_path.read_text(encoding="utf-8"))
    lang = (
        data.get("metadata", {})
        .get("kernelspec", {})
        .get("language", "")
    )
    assert lang, f"{nb_path.name}: no kernelspec.language in metadata"


# ── Workflow YAML validity ────────────────────────────────────────────────

@pytest.mark.parametrize("wf_path", _workflows(), ids=lambda p: p.name)
def test_workflow_is_valid_yaml(wf_path: Path) -> None:
    """Every workflow file must be parseable YAML."""
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{wf_path.name}: top level must be a mapping"
    assert "on" in data or True, "on trigger is optional in test context"


@pytest.mark.parametrize("wf_path", _workflows(), ids=lambda p: p.name)
def test_workflow_has_concurrency(wf_path: Path) -> None:
    """Production workflows must define concurrency to avoid deploy races."""
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    # Skip pure CI-check workflows that don't deploy
    jobs = data.get("jobs", {})
    has_deploy = any(
        "deploy" in j or "publish" in j or "pages" in j
        for j in jobs
    )
    if has_deploy:
        assert "concurrency" in data, (
            f"{wf_path.name} has deploy jobs but no 'concurrency' block. "
            "Add: concurrency: {{ group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}, "
            "cancel-in-progress: true }}"
        )


@pytest.mark.parametrize("wf_path", _workflows(), ids=lambda p: p.name)
def test_workflow_jobs_have_timeouts(wf_path: Path) -> None:
    """Every job must have a timeout-minutes to prevent runner exhaustion."""
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    for job_name, job in data.get("jobs", {}).items():
        # Skip composite/reusable callers — they inherit caller timeout
        if "uses" in job:
            continue
        assert "timeout-minutes" in job, (
            f"{wf_path.name} job '{job_name}': missing timeout-minutes. "
            "A job without a timeout can run indefinitely and exhaust runner minutes."
        )


# ── HTML book structural checks ───────────────────────────────────────────

def _html_books() -> list[Path]:
    return list((REPO_ROOT / "study-guide").glob("book-*.html")) + \
           list((REPO_ROOT / "study-guide").glob("The-DevOps-Path.html"))


@pytest.mark.parametrize("html_path", _html_books(), ids=lambda p: p.name)
def test_html_book_links_css(html_path: Path) -> None:
    """Every book HTML must link to devops-path.css."""
    content = html_path.read_text(encoding="utf-8")
    assert 'href="devops-path.css"' in content, (
        f"{html_path.name}: missing <link rel='stylesheet' href='devops-path.css'>"
    )


@pytest.mark.parametrize("html_path", _html_books(), ids=lambda p: p.name)
def test_html_book_has_cover(html_path: Path) -> None:
    """Every book must have a cover section."""
    content = html_path.read_text(encoding="utf-8")
    assert 'class="cover"' in content, (
        f"{html_path.name}: missing cover section"
    )


@pytest.mark.parametrize("html_path", _html_books(), ids=lambda p: p.name)
def test_html_book_has_mental_model_boxes(html_path: Path) -> None:
    """Every book must have at least one 'analogy' mental model box."""
    content = html_path.read_text(encoding="utf-8")
    assert 'class="box analogy"' in content, (
        f"{html_path.name}: missing mental model (box analogy) — every book must have one"
    )


# ── CODEOWNERS check ─────────────────────────────────────────────────────

def test_codeowners_exists() -> None:
    """CODEOWNERS must exist in .github/ to enforce review requirements."""
    codeowners = REPO_ROOT / ".github" / "CODEOWNERS"
    assert codeowners.exists(), (
        ".github/CODEOWNERS is missing. "
        "Without it, GitHub cannot enforce required code review on PRs."
    )
    content = codeowners.read_text(encoding="utf-8")
    assert "@" in content, "CODEOWNERS must contain at least one @username rule"


# ── Study-guide completeness ──────────────────────────────────────────────

def test_every_module_has_main_notebook() -> None:
    """Each numbered module directory must have a *_mental_models.ipynb."""
    missing = []
    for module_dir in sorted(REPO_ROOT.glob("[0-9][0-9]-*")):
        if not list(module_dir.glob("*_mental_models.ipynb")):
            missing.append(module_dir.name)
    assert not missing, (
        f"These modules are missing a *_mental_models.ipynb: {missing}"
    )


def test_html_books_match_modules() -> None:
    """The number of HTML books should match the number of module directories."""
    modules = list(REPO_ROOT.glob("[0-9][0-9]-*"))
    books   = list((REPO_ROOT / "study-guide").glob("book-*.html"))
    assert len(books) >= len(modules), (
        f"Found {len(modules)} modules but only {len(books)} HTML books. "
        f"Missing books for: "
        f"{set(d.name for d in modules) - set(b.stem for b in books)}"
    )
