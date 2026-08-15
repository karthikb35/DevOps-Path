# Terraform — Interview Questions

> Format: deep-dive architectural questions with model answers and senior gotchas.

---

## Part 1 — Architectural Deep-Dive Questions

### Q1. Someone ran `terraform apply` manually on their laptop against production. How did you detect it? What systemic fix do you make?

**Deep dive.** Detection:
- `terraform plan` on CI will show a diff even though nothing in the HCL changed — the state was updated by the manual apply
- AWS CloudTrail shows API calls from a personal IAM user (not a role used by CI)
- Terraform state `serial` incremented but no CI pipeline ran at that timestamp

**Systemic fix:** Remove the ability for individuals to run `terraform apply` on production:
1. **Service Control Policy (SCP) or IAM policy** that denies Terraform-relevant API calls from human IAM users in the production account. Only the CI service role can call `CreateVpc`, `RunInstances`, etc.
2. **Atlantis or terraform-github-actions** — all applies happen via PR workflow, not local CLI
3. **State file access control** — production S3 state bucket denies write access to all except the CI role
4. **Audit logging** — AWS CloudTrail alerted when IAM user calls the API directly

**The insight:** If the fix is "tell people not to do it," it will happen again. The fix is making the bad behavior technically impossible, not socially discouraged.

---

### Q2. Explain Terraform state and why losing it is catastrophic. How do you protect against state loss?

**Deep dive.** Terraform state maps your HCL resource addresses to real cloud resource IDs:
```
aws_vpc.main → vpc-0a1b2c3d4e5f67890
aws_eks_cluster.main → arn:aws:eks:us-east-1:123:cluster/prod-eks
```

Without state:
- `terraform plan` thinks nothing exists → plan shows CREATE for all resources
- `terraform apply` tries to create duplicate resources (duplicate VPC, duplicate EKS cluster)
- Some will fail (AWS prevents duplicate names), some will succeed (creating orphaned resources)
- You now have two of some things, zero understanding of which is which

**Protection strategy:**
1. **Remote state in S3** with versioning enabled — you can retrieve any previous state version
2. **DynamoDB locking** — prevent concurrent applies that corrupt state
3. **State backup** before any destructive operation: `terraform state pull > backup-$(date +%Y%m%d).tfstate`
4. **Restricted access** — only the CI service role can write to the state bucket
5. **Terraform Cloud** — managed state with version history, auditing, and collaboration built in

**Recovery if state is lost:** `terraform import` — you re-associate existing cloud resources with Terraform state by specifying the resource address and cloud resource ID. It's tedious but recoverable. For a large infrastructure: potentially days of work.

---

### Q3. When does `terraform plan` show no changes, but the infrastructure has actually drifted?

**Deep dive.** Several scenarios:

1. **Config outside Terraform's management:** Someone added a security group rule in the AWS Console. Terraform doesn't know about it — it only manages what's in the state and the config. To detect this: `terraform refresh` updates state from actual AWS, then `plan` shows the drift.

2. **Terraform doesn't model all attributes:** Some resource attributes aren't tracked by the provider. Changes to those don't appear in plan.

3. **Eventually-consistent state:** If you run `plan` immediately after `apply`, some cloud resources (like DNS propagation, certificate validation) may not be in their final state yet. The next `plan` may show changes.

4. **Manual state manipulation:** `terraform state rm`, `terraform import`, or direct state file edits can cause state to diverge from reality.

**Production practice:** Run `terraform plan` on a schedule (nightly via CI) and alert on any unexpected output. This is your drift detection system.

---

### Q4. What is `terraform destroy` and when would you use it?

**Deep dive.** `terraform destroy` removes ALL resources managed by the current state. It is the opposite of `terraform apply`.

**Legitimate use cases:**
- Tearing down a temporary feature environment (ephemeral environments)
- Decommissioning a staging environment
- Cleaning up after a failed experiment
- Cost optimization (dev environments spun down nights/weekends)

**When to NEVER use it:**
- Production infrastructure (always decomission individual resources via HCL changes)
- When you haven't reviewed what will be destroyed first (`terraform plan -destroy`)
- Without a backup of the state file

**Safer alternative:** Rather than `terraform destroy`, manage resource lifecycle with:
```hcl
resource "aws_instance" "dev_server" {
  lifecycle {
    prevent_destroy = true  # Terraform will refuse to destroy this resource
  }
}
```
This prevents accidental `destroy` while allowing planned decommissioning.

---

## Part 2 — Knowledge Check

**Q: What is the purpose of `terraform init`?**
A: Downloads provider plugins specified in `required_providers`, initializes the backend (remote state), and downloads any modules. Must be run before `plan` or `apply`, and after any provider version changes.

**Q: What does `~>` mean in version constraints (e.g., `version = "~> 5.0"`)?**
A: "Pessimistic constraint operator" — allows any version >= 5.0 but < 6.0 (accepts patch and minor, but not major version bumps). `~> 5.17` would allow 5.17+ but < 5.18.

**Q: Explain the difference between `count` and `for_each` for creating multiple resources.**
A: `count` creates N identical resources indexed by integer (`aws_subnet.private[0]`, `[1]`, `[2]`). `for_each` creates resources keyed by map/set keys (`aws_subnet.private["us-east-1a"]`). Use `for_each` when possible — if you remove a `count` element in the middle, Terraform renumbers everything (destructive). `for_each` removes only the specific key.

**Q: What is a data source and how does it differ from a resource?**
A: A `resource` creates/manages a cloud resource. A `data` source reads an existing resource without managing it. Use data sources to: read the current AWS account ID, look up an AMI, reference a VPC created by another Terraform stack.

---

## Part 3 — Senior Gotchas

| Trap | What juniors say | What seniors say |
|---|---|---|
| "State is in the repo" | It's just a JSON file | State contains secrets. Never commit it. Use remote S3/Terraform Cloud. |
| "I'll just delete the state" | It's messing things up | Deleting state orphans real cloud resources. Use `terraform state rm` surgically. |
| "Run apply directly" | It's faster | No PR review, no plan output, no audit trail. Atlantis or CI/CD only. |
| "Use `latest` for modules" | Always up to date | A breaking change in a module breaks every consumer simultaneously. Pin versions. |
| "`terraform destroy` in prod" | Cleanup old resources | `prevent_destroy = true` on critical resources. Destroy via HCL changes, not the destroy command. |
| "Workspaces for prod/staging" | One config, multiple envs | Workspaces share state backend. A mistake in prod workspace can destroy staging's state. Use separate directories + separate state files. |
