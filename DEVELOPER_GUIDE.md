# Developer Guide

## 1. Purpose

This repository uses automated checks to keep code, documentation, study-guide content, GitHub Actions workflows, and generated PDFs consistent and safe.

Before opening a pull request, developers should run the local checks described below.

The repository uses:

* **uv** for Python environment and dependency management
* **Ruff** for linting and formatting
* **pytest** for structural and repository protection tests
* **yamllint** for YAML validation
* **pre-commit** for automated local checks
* **Playwright + Chromium** for HTML-to-PDF rendering
* **GitHub Actions** for CI, PDF generation, security scanning, and GitHub Pages deployment

---

# 2. Required Development Environment

The project requires:

* Python **3.11 or newer**
* `uv`
* Git
* A working internet connection for installing dependencies

The project configuration specifies:

```toml
requires-python = ">=3.11"
```

## Install uv

Install `uv` using the official installation method for your operating system.

After installation, verify:

```bash
uv --version
```

## Install project dependencies

From the repository root:

```bash
uv sync --dev
```

This creates/updates the project's `.venv` environment and installs the development dependencies.

Verify the environment:

```bash
uv run python --version
```

---

# 3. Development Dependencies

The development environment includes:

| Tool         | Purpose                               |
| ------------ | ------------------------------------- |
| `ruff`       | Python linting and formatting         |
| `pytest`     | Automated tests                       |
| `pytest-cov` | Test coverage                         |
| `pyyaml`     | YAML parsing/validation used by tests |
| `yamllint`   | YAML style and syntax validation      |
| `pre-commit` | Local automated checks                |
| `playwright` | HTML/PDF rendering                    |

Dependencies are defined in `pyproject.toml` and should normally be installed with:

```bash
uv sync --dev
```

Do not manually create a separate Python virtual environment unless there is a specific reason to do so.

---

# 4. Pre-Commit Hooks

The repository uses **pre-commit** to catch problems before they reach CI.

Install the hooks:

```bash
uv run pre-commit install
```

Run all hooks manually:

```bash
uv run pre-commit run --all-files
```

The configured hooks cover:

## Ruff linting

Ruff checks Python code and automatically applies supported fixes.

```text
ruff check
```

The hook is configured with:

```text
--fix
--exit-non-zero-on-fix
```

This means that if Ruff modifies a file, the hook exits unsuccessfully so that you can inspect the changes and commit them separately.

## Ruff formatting

The repository also runs:

```text
ruff format
```

Python files must conform to Ruff's formatting rules.

## uv lockfile consistency

The repository checks:

```bash
uv sync --frozen --check
```

This ensures that changes to `pyproject.toml` are reflected in `uv.lock`.

If you change dependencies in `pyproject.toml`, regenerate the lockfile:

```bash
uv lock
```

Then run:

```bash
uv sync --dev
```

## pytest protection tests

The pre-commit configuration runs the protection tests during `pre-push`:

```bash
uv run pytest tests/ -q --tb=short
```

These tests are intentionally run on push rather than every commit because they may take longer than the normal formatting/linting hooks.

## General file hygiene

The repository also checks:

* Large files
* YAML syntax
* End-of-file newlines
* Trailing whitespace
* Mixed line endings
* JSON validity
* Merge-conflict markers

Notebook (`.ipynb`) files are also JSON and therefore covered by the JSON validation.

---

# 5. Python Linting

Ruff is the primary Python linting tool.

Run:

```bash
uv run ruff check .
```

If Ruff reports problems that it can automatically fix:

```bash
uv run ruff check . --fix
```

After fixing, run the check again:

```bash
uv run ruff check .
```

CI also runs Ruff with GitHub-compatible output:

```bash
uvx ruff check . --output-format=github
```

A pull request must pass the Ruff lint check.

---

# 6. Python Formatting

Ruff is also responsible for Python formatting.

Check formatting without modifying files:

```bash
uv run ruff format --check .
```

If formatting changes are required:

```bash
uv run ruff format .
```

Then verify:

```bash
uv run ruff format --check .
```

Do not rely on CI to automatically format your code. CI checks formatting but does not modify the repository.

---

# 7. Import Ordering

Import ordering is enforced separately in CI.

The repository uses Ruff's `I` rules, which replace the need for a separate isort CI implementation.

Run locally:

```bash
uv run ruff check . --select I
```

If imports need fixing:

```bash
uv run ruff check . --select I --fix
```

The CI job is named:

```text
Import Order (isort via ruff)
```

This is a separate required check so that import-order failures are visible independently.

---

# 8. Running Tests

Run the complete protection test suite:

```bash
uv run pytest tests/ -v --tb=short
```

The project is configured with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

The tests are repository-protection tests rather than only application-unit tests.

They may validate things such as:

* Notebook JSON validity
* Absence of committed generated outputs
* Workflow YAML structure
* HTML study-guide structure
* `CODEOWNERS` presence
* Required modules/files
* Repository completeness

A failing protection test should be investigated before opening a pull request.

---

# 9. YAML Validation

GitHub Actions workflow files are checked with `yamllint`.

Run against the workflow directory:

```bash
uv run yamllint .github/workflows/
```

The CI configuration allows a maximum line length of 140 characters.

It also explicitly permits the YAML values:

```text
true
false
on
```

If you modify a workflow file, always run the YAML lint check locally.

---

# 10. GitHub Actions Workflows

The repository contains several automated workflows.

## CI

The main CI workflow runs on:

* Pushes to `main`
* Pull requests

It contains separate checks for:

1. Ruff linting and formatting
2. Import ordering
3. Protection tests
4. YAML linting
5. Secret detection

All relevant CI checks must pass before a pull request can be merged.

---

# 11. Security / Secret Detection

Pull requests are scanned for accidentally committed secrets using TruffleHog.

The scan looks for things such as:

* API keys
* Tokens
* Passwords
* Credentials
* Secrets embedded in source files
* Secrets in YAML
* Secrets in notebooks

Never commit real credentials to the repository.

If a secret is accidentally committed:

1. Do not simply delete it from the latest commit.
2. Assume it may have been exposed.
3. Revoke/rotate the credential.
4. Notify the appropriate repository owner.
5. Remove the secret from repository history when required.

Use environment variables or GitHub Actions secrets for credentials.

---

# 12. GitHub Actions Workflow Changes

When modifying files under:

```text
.github/workflows/
```

check:

```bash
uv run yamllint .github/workflows/
```

Then run:

```bash
uv run pre-commit run --all-files
```

Pay particular attention to:

* `on:` triggers
* Job dependencies
* Permissions
* Secrets
* Artifact names
* Release tags
* Conditional expressions
* Python versions
* Action versions

Workflow files are executable infrastructure and should be reviewed accordingly.

---

# 13. Study-Guide HTML

The study-guide books are stored under:

```text
study-guide/
```

The repository contains individual books plus a master study guide.

The PDF workflow currently handles:

* Book 1 — Git & GitHub Actions
* Book 2 — Jenkins
* Book 3 — Docker
* Book 4 — Kubernetes
* Book 5 — Ansible
* Book 6 — Terraform
* Book 7 — Monitoring & Observability
* Book 8 — Branch Protection & CI Checks
* Master — The DevOps Path

When modifying a study-guide HTML file, check that:

* The HTML remains valid.
* Links still work.
* Images/resources are available.
* The shared CSS is still applied.
* Headings and navigation remain consistent.
* No unintended generated files are committed.

---

# 14. PDF Generation

PDFs are generated by the `docs-pdf.yml` GitHub Actions workflow.

The workflow uses:

* Python 3.12
* Playwright
* Headless Chromium
* Noto Color Emoji fonts
* Liberation fonts

The renderer is:

```text
study-guide/render_pdf.py
```

The workflow detects which books changed.

A book is rebuilt when:

* Its HTML changed.
* Shared CSS changed.
* The PDF renderer changed.
* The PDF workflow changed.
* `force_all` was requested manually.

Otherwise, the previous PDF is reused from the rolling:

```text
devops-pdfs
```

release.

This prevents unnecessary PDF rendering.

---

# 15. Forcing a Full PDF Rebuild

The PDF workflow supports manual execution through GitHub Actions.

When manually starting the workflow, the:

```text
force_all
```

option can be enabled.

This causes every book PDF to be rebuilt regardless of detected changes.

Use this when:

* The PDF renderer changes.
* Chromium/font behavior changes.
* Shared rendering behavior changes.
* You need to regenerate every PDF deliberately.

---

# 16. GitHub Pages

The Pages workflow builds the study-guide website.

The site contains:

* An index page
* Individual HTML books
* Shared CSS
* Links to the generated PDFs

The site is assembled into:

```text
_site/
```

The index is generated with:

```bash
python study-guide/build_index.py _site/
```

The site is deployed using GitHub Pages Actions.

Pages requires the workflow permissions:

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

The deployment uses GitHub's OIDC-based authentication rather than a manually stored deployment credential.

---

# 17. Pull Request Requirements

Before opening a pull request, run the following:

```bash
uv sync --dev

uv run pre-commit run --all-files

uv run pytest tests/ -v --tb=short

uv run ruff check .

uv run ruff format --check .

uv run ruff check . --select I

uv run yamllint .github/workflows/
```

If all checks pass locally, push the branch and wait for GitHub Actions to complete.

The pull request should not be merged while required CI checks are failing.

---

# 18. Recommended Developer Workflow

A normal development cycle should look like this:

## Step 1 — Create a branch

```bash
git checkout -b feature/my-change
```

## Step 2 — Make the change

Modify the required source, documentation, tests, or study-guide files.

## Step 3 — Sync dependencies

If `pyproject.toml` changed:

```bash
uv lock
uv sync --dev
```

## Step 4 — Run formatting

```bash
uv run ruff format .
```

## Step 5 — Run linting

```bash
uv run ruff check . --fix
```

## Step 6 — Check imports

```bash
uv run ruff check . --select I
```

## Step 7 — Run tests

```bash
uv run pytest tests/ -v --tb=short
```

## Step 8 — Validate workflows

If workflow files were changed:

```bash
uv run yamllint .github/workflows/
```

## Step 9 — Run all pre-commit hooks

```bash
uv run pre-commit run --all-files
```

## Step 10 — Review the changes

```bash
git status
git diff
```

Make sure no unwanted files, credentials, PDFs, caches, `.venv`, or generated artifacts have been added.

## Step 11 — Commit

```bash
git add .
git commit -m "Describe the change"
```

## Step 12 — Push

```bash
git push -u origin feature/my-change
```

Then open the pull request.

---

# 19. Files Developers Should Generally Not Commit

Do not commit development-generated files such as:

```text
.venv/
__pycache__/
.pytest_cache/
.coverage
*.pyc
```

Generated PDFs should only be committed if the repository explicitly requires them to be version-controlled.

The normal PDF workflow publishes generated PDFs through the rolling `devops-pdfs` release rather than requiring them to be committed to source control.

---

# 20. Dependency Changes

If you add, remove, or update a Python dependency:

1. Modify the dependency configuration.
2. Regenerate `uv.lock`.
3. Run `uv sync --dev`.
4. Run the tests.
5. Run pre-commit.
6. Commit both dependency configuration and the updated lockfile.

For example:

```bash
uv lock
uv sync --dev
uv run pytest tests/ -v --tb=short
uv run pre-commit run --all-files
```

The `uv-sync-check` pre-commit hook is specifically intended to detect stale lockfiles.

---

# 21. What CI Protects

The repository's automated checks provide several layers of protection.

| Area              | Protection                     |
| ----------------- | ------------------------------ |
| Python            | Ruff linting                   |
| Python formatting | Ruff format                    |
| Imports           | Ruff `I` rules                 |
| Tests             | pytest protection suite        |
| YAML              | yamllint                       |
| JSON / notebooks  | pre-commit JSON validation     |
| Large files       | pre-commit large-file check    |
| Whitespace        | trailing-whitespace hook       |
| Line endings      | mixed-line-ending hook         |
| Merge conflicts   | merge-conflict hook            |
| Dependencies      | uv lockfile consistency        |
| Secrets           | TruffleHog                     |
| HTML books        | repository protection tests    |
| PDFs              | Automated Playwright rendering |
| Website           | GitHub Pages workflow          |

---

# 22. Definition of Done

A change is ready for merge when:

* [ ] The requested change is implemented.
* [ ] Tests have been added or updated when appropriate.
* [ ] `uv sync --dev` succeeds.
* [ ] `uv run ruff check .` passes.
* [ ] `uv run ruff format --check .` passes.
* [ ] `uv run ruff check . --select I` passes.
* [ ] `uv run pytest tests/ -v --tb=short` passes.
* [ ] `uv run yamllint .github/workflows/` passes when workflow files are relevant.
* [ ] `uv run pre-commit run --all-files` passes.
* [ ] No secrets or credentials are committed.
* [ ] No unintended generated files are committed.
* [ ] `uv.lock` is updated when dependencies change.
* [ ] GitHub Actions required checks pass.
* [ ] The pull request has been reviewed and is ready to merge.

---

# 23. Quick Command Reference

### Setup

```bash
uv sync --dev
uv run pre-commit install
```

### Format

```bash
uv run ruff format .
```

### Lint

```bash
uv run ruff check .
```

### Auto-fix lint issues

```bash
uv run ruff check . --fix
```

### Import ordering

```bash
uv run ruff check . --select I
```

### Tests

```bash
uv run pytest tests/ -v --tb=short
```

### YAML

```bash
uv run yamllint .github/workflows/
```

### All pre-commit checks

```bash
uv run pre-commit run --all-files
```

### Dependency synchronization

```bash
uv lock
uv sync --dev
```

### Final local verification

```bash
uv run pre-commit run --all-files
uv run pytest tests/ -v --tb=short
uv run ruff check .
uv run ruff format --check .
uv run ruff check . --select I
uv run yamllint .github/workflows/
```

---

# 24. Important Principle

**CI is the final gate, not the first place to discover problems.**

Developers should run the relevant checks locally before pushing.

A good pull request should arrive at CI already passing:

```text
Format → Lint → Import Check → Tests → YAML Check → Security Scan → Review → Merge
```

The automated workflows provide the final independent verification that the repository remains healthy.
