# Git & GitHub Actions — Architectural Notes

> The senior architect's lens: not "how do I commit code" but "how do I design a
> version control and automation system that scales with a 200-engineer org without
> becoming a bottleneck or a single point of failure."

---

## The Core Mental Model: Git Is a Distributed Append-Only Log

Every Git repository is a **content-addressed, immutable, append-only DAG** (directed
acyclic graph). Each commit is a SHA-256 hash of its content + parent hash. This
gives you:

- **Integrity by construction** — you cannot silently alter history
- **Distributed by default** — every clone is a complete backup
- **Cheap branches** — a branch is just a pointer (40 bytes) to a commit SHA

The implication for architecture: **Git is not a deployment tool, it is a source of truth**.
Triggering deployments from git events (push, PR merge) is the correct mental model —
not SSH-ing into a server and pulling code directly.

---

## Branching Strategy Trade-offs

### GitFlow
```
main ─────────────────────────────────── v1.0 ─── v2.0
          ↑ release branches               ↑
develop ──────────────────────────────────────────────
     ↑                   ↑
  feature/*           feature/*
```
**Use when:** Long release cycles, multiple parallel versions in production (SaaS with enterprise customers on v1 while v2 ships)  
**Avoid when:** Continuous delivery teams — the overhead of long-lived branches is anti-CD

### GitHub Flow (trunk-based light)
```
main ──────────────────────────────────── (always deployable)
       ↑ short-lived feature branches
```
**Use when:** Teams deploying multiple times per day  
**Avoid when:** You need to maintain multiple production versions simultaneously

### Trunk-Based Development
```
main (trunk) ─── commits every few hours, feature flags gate incomplete work
```
**Use when:** Elite engineering orgs (Google, Facebook) with strong feature flag infrastructure  
**Risk:** Requires discipline — bad commits hit main immediately

---

## GitHub Actions: The Architecture Decisions That Matter

### Runners
| Runner Type | Cost | Isolation | Use case |
|---|---|---|---|
| GitHub-hosted (ubuntu-latest) | Included (limits) | Full VM per job | Most CI workloads |
| Self-hosted | Your infra | Shared/dedicated | Private network, GPU, compliance |
| Larger runners | $$$ | Full VM | Compilation-heavy, ML |

**Production decision:** GitHub-hosted for open-source and most teams. Self-hosted
only when you need: VPC access to private databases, specific hardware (GPU/ARM),
or regulatory compliance that prohibits external runners.

### Secrets Management Architecture
```
❌ WRONG:  Environment variables hardcoded in workflow YAML
❌ WRONG:  .env file committed to repo (even "private" repos)
✅ RIGHT:  GitHub Encrypted Secrets + OIDC for cloud auth (no long-lived keys)
✅ BETTER: External secrets manager (HashiCorp Vault, AWS Secrets Manager) + short-lived tokens
```

**OIDC (OpenID Connect) is the gold standard:** GitHub Actions can get a short-lived
AWS/GCP/Azure token via OIDC without storing *any* credentials. The cloud provider
trusts GitHub's identity assertion. No secret rotation needed.

### Workflow Triggering: When to Use What
| Trigger | Use case | Pitfall |
|---|---|---|
| `push` to main | Deploy to prod | Too broad — triggers on every README change |
| `pull_request` | Run tests/lint | OK for most teams |
| `workflow_dispatch` | Manual release | Good safety valve |
| `schedule` (cron) | Nightly scans, DB backups | Will fail silently if repo is inactive |
| `repository_dispatch` | External systems trigger CI | Needed for multi-repo architectures |
| `workflow_call` | Reusable workflows | The correct pattern for DRY pipelines |

---

## The CI/CD Pipeline Design Principles

### 1. The Pipeline is a Quality Gate, Not a Deployment Script
A pipeline should **prevent bad code from reaching the next stage**. Each stage is a gate:

```
Code → [lint] → [unit tests] → [build] → [integration tests] → [security scan] → [deploy staging] → [smoke tests] → [deploy prod]
         ↓fail      ↓fail         ↓fail         ↓fail                ↓fail              ↓fail              ↓fail
       Stop       Stop           Stop           Stop                 Stop               Stop                Stop
```

### 2. Fast Feedback Over Thoroughness
- The first 2 minutes: lint + unit tests (fast, cheap, catches 80% of issues)
- Minutes 5-10: integration tests, build
- Minutes 10-20: security scans, performance tests
- Never: tests that take >30 minutes before feedback on a PR (engineers bypass them)

### 3. Idempotent Pipelines
Every pipeline run with the same inputs must produce the same outputs. Flaky tests,
non-deterministic builds, and time-based checks violate this.

**Tactics for idempotency:**
- Pin all dependency versions (exact SHAs, not `latest`)
- Pin action versions (`uses: actions/checkout@v4.1.1`, not `@main`)
- Hermetic builds (Docker, Nix, Bazel)
- No side effects in test setup (use test fixtures, not production data)

### 4. The Secret to Fast Pipelines: Parallelism + Caching
```yaml
# ❌ Sequential (slow)
steps:
  - run: pytest unit/
  - run: pytest integration/
  - run: npm test

# ✅ Parallel jobs (fast)
jobs:
  python-unit:   { runs-on: ubuntu-latest, steps: [pytest unit/] }
  python-integ:  { runs-on: ubuntu-latest, steps: [pytest integration/] }
  js-tests:      { runs-on: ubuntu-latest, steps: [npm test] }
  # All 3 run simultaneously
```

### 5. Security is Not Optional in Pipelines
Every pipeline should include (ordered by blast radius):
1. **Dependency audit** (`pip audit`, `npm audit`, `trivy fs`) — catches CVEs before you ship them
2. **SAST** (static analysis: `bandit` for Python, `semgrep`) — catches insecure code patterns
3. **Container scanning** (`trivy image`, `grype`) — catches OS-level CVEs in your base image
4. **Secret scanning** (`trufflesecurity`, `detect-secrets`) — prevents credential leaks

---

## Failure Modes and Mitigations

| Failure | Why it happens | Mitigation |
|---|---|---|
| Pipeline flakiness | Non-deterministic tests, timing issues | Retry transient failures, fix flaky tests — never just re-run |
| Secret exposure in logs | `echo $SECRET` in step | Use `::add-mask::` directive; never echo secrets |
| Supply chain attack | Compromised Action or dependency | Pin to SHA (`uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`), use Dependabot |
| Long-running pipelines | Slow tests, sequential jobs | Parallelize, add timeouts per job |
| Noisy alerts on PR | Every push triggers full suite | Use path filters — only run what changed |
| Deployment race conditions | Two PRs merge simultaneously | Concurrency groups + `cancel-in-progress` |

---

## Connections Across the DevOps Repo

- **Module 02 (Jenkins):** The same pipeline design principles apply, but with Groovy DSL and a persistent server
- **Module 03 (Docker):** GitHub Actions builds Docker images; the build is the artifact
- **Module 04 (Kubernetes):** Actions deploy to K8s via `kubectl`/Helm; ArgoCD adds GitOps pull model
- **Module 06 (Terraform):** Atlantis and `terraform-github-actions` put IaC in the same pipeline model
