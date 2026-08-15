# Docker — Architectural Notes

> The senior architect's lens: not "how do I run a container" but "how do I design a
> container strategy that is secure, efficient, and operable at scale."

---

## Containers Are Not Mini-VMs — The Architectural Consequence

The #1 mistake engineers make with containers: treating them like lightweight VMs that
you SSH into to change configuration. A container should be **immutable**. Configuration
happens at build time (Dockerfile) or at runtime via environment variables. You never
`docker exec` into a production container to change a file — that change disappears on
the next deploy.

**Immutable containers → reproducible deployments.** The same image behaves identically
in dev, CI, staging, and production. "Works in staging" becomes provably true.

---

## The Image Size Trade-off

Every byte in your image:
1. Takes time to push/pull from registry
2. Occupies disk on every node
3. Increases the attack surface (more code = more CVEs)
4. Increases container startup time

**Production rule:** Challenge every layer in your Dockerfile. If a package was needed
only during compilation, it belongs in a builder stage, not the final image.

Reference sizes (targets, not guarantees):
- Python API: 100-200MB (slim base + app + deps)
- Go binary: 5-50MB (scratch + binary)
- Java service: 100-300MB (distroless + JAR)
- Node.js API: 100-200MB (slim + prod deps only)

---

## The Security Posture Model

Containers reduce surface area through several mechanisms. Used together:

```
Threat: Attacker exploits app-level vulnerability
                    ↓
App runs as nonroot (UID 1001)
  → Can't write outside /tmp, /app/logs
                    ↓
Read-only root filesystem
  → Can't install tools, can't modify binary
                    ↓
No NET_RAW, no SYS_ADMIN, capabilities dropped
  → Can't run raw sockets, can't modify kernel params
                    ↓
No new privileges flag
  → Can't gain root via setuid binaries
                    ↓
Network policy (K8s layer)
  → Can only reach allowed services
```

Each layer is defense in depth. Adversaries need to break ALL layers, not just one.

---

## Volume Patterns

| Pattern | When | Example |
|---|---|---|
| **Named volume** | Persistent data that must survive container restart | `postgres-data:/var/lib/postgresql/data` |
| **Bind mount (dev)** | Hot-reload in development | `./src:/app/src:ro` |
| **tmpfs** | Ephemeral sensitive data (don't write to disk) | `--tmpfs /tmp` |
| **No volume** | Truly stateless service | Most microservices |

**The stateless principle:** Containers should be designed to run without persistent volumes.
State belongs in external services (databases, Redis, S3). A container that needs a volume
for application state is an anti-pattern — that data disappears on restart.

---

## Docker in CI vs Docker in Production

| Concern | CI (Building images) | Production (Running containers) |
|---|---|---|
| **Caching** | BuildKit layer cache → fast rebuilds | Not relevant |
| **Multi-arch** | `--platform linux/amd64,arm64` | Match host arch |
| **Registry** | Push to ECR/GHCR | Pull from ECR/GHCR |
| **Security** | Build-time secret scanning (trivy) | Runtime isolation + seccomp |
| **Build secrets** | `--secret id=key,env=KEY` (not ARG) | N/A |

---

## The Transition to Kubernetes

Docker Compose is the local development standard. But in production:
- Compose has no self-healing
- Compose has no horizontal scaling
- Compose has no cross-host networking
- Compose has no RBAC

Kubernetes is Compose + all of the above. The mental model you build with
Compose (services, networks, volumes, health checks) maps directly to K8s
(Services, NetworkPolicies, PVs, probes). The transition is conceptual, not a restart.

## Connections Across the DevOps Repo

- **Module 01 (GitHub Actions):** Builds the Docker image; the pipeline artifact IS the image
- **Module 04 (Kubernetes):** Runs the Docker image at scale; K8s pulls from the registry
- **Module 06 (Terraform):** Provisions the ECR/GCR registry and node infrastructure
- **Module 07 (Monitoring):** Container logs → Fluent Bit → ELK; metrics from `/metrics`
