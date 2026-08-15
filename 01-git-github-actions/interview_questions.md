# Git & GitHub Actions — Interview Questions

> Format: deep-dive architectural questions with model answers, a knowledge check,
> and a "gotchas" section that trips up senior candidates.

---

## Part 1 — Architectural Deep-Dive Questions

### Q1. Your team has 50 engineers pushing to a monorepo. PRs take 45 minutes to get CI feedback. What's your diagnosis and fix?

**Deep dive.** A 45-minute feedback loop breaks the DORA metric of "fast feedback" and
causes engineers to batch changes (larger PRs = more blast radius). Diagnosis checklist:

1. **Are jobs sequential when they could be parallel?** Run lint, unit tests, and
   integration tests as parallel jobs. If your test suite has 3 suites running sequentially,
   parallelizing is free and gives 3× speedup.
2. **Is caching missing or stale?** Dependencies (pip, npm, Maven) that are reinstalled
   on every run are the #1 silent time killer. Cache using a lockfile hash.
3. **Are all tests running for every change?** In a monorepo, only the services that
   *changed* need their tests run. Use `dorny/paths-filter` or Nx/Turborepo affected
   commands to scope test runs to changed paths.
4. **Are tests inherently slow?** Integration tests hitting real databases are 10-100×
   slower than mocks. Use testcontainers or an in-memory DB for speed.
5. **Is the base Docker image being rebuilt instead of pulled?** Cache layers and use a
   registry to store intermediate build artifacts.

**Model answer:** Parallelize jobs → add dependency caching → implement path-based
filtering → move slow integration tests to a separate nightly pipeline with only smoke
tests on PR.

---

### Q2. A developer accidentally committed an AWS secret key. What do you do, in what order, and what systemic changes do you make?

**Deep dive.** The secret is compromised the moment it is pushed. Assume it was already
scraped by bots scanning GitHub in real time (they do this within seconds).

**Immediate response (first 5 minutes):**
1. **Revoke the credential immediately** in AWS IAM — before doing anything else. The
   code is not the threat; the working credential is the threat.
2. Audit CloudTrail/IAM logs for any activity on that key since the commit timestamp.
3. Remove the secret from Git history using `git filter-repo` (not `filter-branch`).
4. Force-push the cleaned history.
5. Notify the security team regardless of whether you found any unauthorized usage.

**Systemic changes:**
- Enable **pre-commit hooks** with `detect-secrets` to prevent this in the future.
- Enforce GitHub's **secret scanning push protection** (it blocks pushes with known secret patterns).
- Move to **OIDC** for cloud authentication — no long-lived keys stored anywhere.
- Add a secret scanning step in every CI pipeline.

**The key insight:** Tools catch most secrets at the static pattern level. The real fix
is eliminating the class of secrets entirely via OIDC and short-lived credentials.

---

### Q3. What is OIDC in the context of GitHub Actions, why does it matter, and how does it work?

**Deep dive.** OIDC (OpenID Connect) is an identity protocol that lets GitHub Actions
prove its identity to cloud providers (AWS, GCP, Azure) without storing long-lived
credentials anywhere.

**How it works:**
```
GitHub Actions job starts
        ↓
GitHub issues a short-lived OIDC JWT token (signed, expires in minutes)
        ↓
Workflow calls AWS STS AssumeRoleWithWebIdentity, presenting the JWT
        ↓
AWS verifies the JWT signature against GitHub's public OIDC endpoint
        ↓
AWS issues a short-lived IAM role credential (15min - 1hr)
        ↓
Workflow uses the credential to deploy — credential expires after the job
```

**Why it matters:**
- No AWS access keys stored in GitHub Secrets (no rotation, no leakage)
- Every job gets a fresh token with minimal permissions
- Compromise of a job's token is time-limited — useless after the job ends
- Audit trail in AWS CloudTrail shows exactly which GitHub workflow accessed what

---

### Q4. Explain trunk-based development vs GitFlow. When does each break down?

**Deep dive.**

**Trunk-Based Development** — all engineers commit directly to `main` (or via very
short-lived branches, <1 day). Incomplete features are hidden by feature flags.

- **Works when:** Strong automated testing, feature flag infrastructure, high
  deployment frequency (10+ deploys/day), senior team with discipline.
- **Breaks down when:** No feature flags (half-finished features ship), slow or no
  automated tests (bad commits hit main directly), teams with low trust levels.

**GitFlow** — `main` (stable) + `develop` (integration) + `feature/*` (in progress) +
`release/*` (prep) + `hotfix/*` (emergency).

- **Works when:** Multiple versions in production simultaneously (enterprise software
  with long-term support), infrequent releases, compliance requirements demanding
  release candidates.
- **Breaks down when:** CI/CD teams — the overhead of merge coordination across
  long-lived branches (merge conflicts, integration hell, delayed feedback) is
  anti-continuous delivery. A 2-week feature branch that merges into `develop` then
  waits for a release branch means 3-week feedback loops.

**The senior answer:** "The best branching strategy is the one your team consistently
follows. But for a team doing continuous delivery, trunk-based with feature flags
reduces merge complexity and accelerates feedback. For a SaaS company maintaining
v3, v4, and v5 simultaneously, GitFlow's release branches are a genuine necessity."

---

### Q5. How do you prevent a bad deployment from reaching production in a GitHub Actions pipeline?

**Deep dive.** Defense in depth — multiple gates, each catching different failure classes:

```
Gate 1 — Pre-merge (PR required checks):
  lint → unit tests → SAST → dependency audit
  Branch protection: no merge without green required checks

Gate 2 — Post-merge to main:
  build + integration tests → container scan → staging deploy + smoke tests
  If any gate fails: pipeline stops, on-call notified

Gate 3 — Deployment strategy:
  Canary: 5% traffic → metrics 15min → 50% → 100%
  Feature flags: toggle off without redeployment if metric degrades
  Rollback: automatic if error rate > threshold (monitored via Datadog/Grafana)

Gate 4 — Post-deployment:
  Automated synthetic tests hitting production endpoints
  Latency/error rate alarms — auto-rollback if p99 spikes
```

**The architectural principle:** Every gate should be automated. Manual approval gates
are acceptable for prod deployments at regulated companies, but they should be the
exception, not the primary safety mechanism.

---

## Part 2 — Knowledge Check

**Q: What does `git rebase -i HEAD~5` do?**  
A: Opens an interactive rebase for the last 5 commits, letting you squash, reorder, edit, or drop them. Changes history — never rebase commits that are already pushed to a shared branch.

**Q: What is the difference between `git merge` and `git rebase`?**  
A: `merge` creates a merge commit preserving both histories (non-destructive). `rebase` replays your commits on top of the target branch (clean linear history, but rewrites SHAs — dangerous on shared branches).

**Q: What happens if two workflows run simultaneously and both try to deploy to prod?**  
A: Race condition — one may overwrite the other or both may partially apply. Fix: `concurrency: group: prod-deploy` in workflow YAML with `cancel-in-progress: true` or `false` depending on whether you want to queue or cancel.

**Q: How do you securely pass a secret to a Docker build?**  
A: Use Docker BuildKit secrets (`--secret id=mysecret,src=<(echo $SECRET)`) or build args only for non-sensitive values. Never `ARG SECRET_KEY` — build args are persisted in the image layer history.

**Q: What is a composite action vs a reusable workflow?**  
A: Composite action = a sequence of steps packaged as a single step (runs in the caller's job). Reusable workflow = a full workflow with its own jobs and runners, called via `workflow_call`. Use composite for step-level reuse; use reusable workflows for job-level reuse across repositories.

---

## Part 3 — Senior Gotchas

| Trap | What juniors say | What seniors say |
|---|---|---|
| "We need to speed up CI" | Add more RAM to the runner | Parallelize jobs, add caching, scope tests to changed paths |
| "Let's just use `latest` for actions" | It's always up to date | It's a supply chain attack vector — pin to SHA |
| "Our deployment is automated" | We push to main and it deploys | What's the rollback procedure? How long does it take? Is it tested? |
| "We use GitHub Secrets for AWS keys" | That's secure | OIDC eliminates the credential entirely — no rotation, no leakage |
| "Branch protection is enough" | PRs require approval | What prevents an admin from bypassing it? Audit log + CODEOWNERS for sensitive paths |
| "Tests pass on my machine" | Reproduce locally | The pipeline IS the definition of passing — local is anecdote, CI is evidence |
