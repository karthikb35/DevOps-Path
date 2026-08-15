# Kubernetes — Interview Questions

> Format: deep-dive architectural questions with model answers, a knowledge check,
> and a "gotchas" section that trips up senior candidates.

---

## Part 1 — Architectural Deep-Dive Questions

### Q1. A pod is stuck in `CrashLoopBackOff`. Walk me through your exact debugging approach.

**Deep dive.** CrashLoopBackOff means the container is repeatedly crashing and Kubernetes
is applying exponential backoff before restarting it. Diagnostic sequence:

1. `kubectl describe pod <pod-name>` — check the Events section. The last few events
   show: was it OOMKilled (memory limit)? Exit code 1 (app crash)? Exit code 137 (SIGKILL)?
2. `kubectl logs <pod-name> --previous` — the `--previous` flag shows logs from the
   LAST crashed container (critical — the current container has no logs yet).
3. Check exit code: `describe pod` shows `Last State: exitCode: 137` → OOMKill.
   Increase memory limit. Exit code 1 → application error. Read previous logs.
4. `kubectl exec -it <pod-name> -- /bin/sh` → if you can get a shell, run the app
   manually to reproduce the error.

**Exit code cheatsheet:**
- `0`: clean exit (not a crash)
- `1`: application error (check logs)
- `137`: OOMKilled OR `kill -9` (check if memory limit too low)
- `139`: Segfault (binary or memory corruption)
- `143`: SIGTERM (graceful termination, pod was stopping normally)

---

### Q2. Explain the difference between readinessProbe and livenessProbe. Give an example of where setting them incorrectly causes an outage.

**Deep dive.** The probes serve different purposes:

**ReadinessProbe:** "Is this pod ready to receive traffic?"
- Failing readiness → pod removed from Service endpoints (no traffic routed to it)
- Pod is NOT restarted
- Use for: slow startup, cache warming, DB connection not ready

**LivenessProbe:** "Is this pod alive/healthy?"
- Failing liveness → pod is KILLED and restarted
- Use for: deadlocks, infinite loops, genuinely hung processes

**Outage scenario 1 — Liveness probe checks DB:**
```yaml
livenessProbe:
  httpGet:
    path: /health/db  # ← checks database connectivity
```
DB goes down for maintenance. All pods fail their liveness probe simultaneously. All 20 pods restart. During restart, zero pods are serving traffic. Outage.
Fix: liveness should only check the app's own health (memory, event loop). Not downstream dependencies.

**Outage scenario 2 — Missing startupProbe:**
```yaml
livenessProbe:
  initialDelaySeconds: 5  # ← too short for a slow-starting JVM app
```
Java Spring Boot app takes 45 seconds to start. Liveness probe starts checking at 5 seconds. Finds app not ready (still starting). Kills it. New pod starts. Gets killed at 5 seconds. Infinite loop. Fix: `startupProbe` with `failureThreshold: 30` and `periodSeconds: 10` = 5-minute window for startup.

---

### Q3. What is the difference between a Deployment and a StatefulSet? When would you use each?

**Deep dive.**

**Deployment:** For stateless workloads.
- Pods are interchangeable (any pod can handle any request)
- Pod names are random: `nginx-7d4f9c-xk2p1`, `nginx-7d4f9c-ab3q7`
- Can be scaled up/down freely
- Rolling updates replace pods in any order
- Example: API servers, web frontends, worker processes

**StatefulSet:** For stateful workloads needing stable identity and ordered operations.
- Pods have stable, ordered names: `mysql-0`, `mysql-1`, `mysql-2`
- `mysql-0` always comes up before `mysql-1` (ordered startup)
- Each pod gets its own PersistentVolumeClaim (stable storage)
- Pod is deleted and recreated with the SAME name (stable identity)
- Example: databases (MySQL, Cassandra, Elasticsearch), Kafka, ZooKeeper

**When StatefulSet is necessary:**
- The application needs stable network identity (peers connect to each other by hostname)
- Each instance needs its own persistent storage
- Ordered startup/shutdown is required (replica connects to primary which must be up first)

**Senior caveat:** Running databases in Kubernetes is harder than running them as managed services (RDS, Cloud SQL). The StatefulSet handles stable identity and storage, but you still need to handle: leader election, replication, backup, point-in-time recovery. For most teams: use managed databases (RDS, Cloud SQL) and reserve StatefulSets for when you genuinely need them.

---

### Q4. How does a Kubernetes Service know which pods to send traffic to? What happens when a pod is unhealthy?

**Deep dive.** Services use label selectors. The Endpoints controller watches for pods that match the selector and maintains a list of their IPs in an `Endpoints` object.

```yaml
# Service selector:
selector:
  app: payment-service  # ← only pods with this label

# Pod labels:
labels:
  app: payment-service  # ← this pod is selected
```

When a pod's `readinessProbe` fails:
1. Kubelet detects the probe failure
2. Kubelet marks the pod's `Ready` condition as `False`
3. The Endpoints controller sees the pod is `NotReady`
4. **The Endpoints controller removes the pod's IP from the Service's Endpoints object**
5. kube-proxy (or eBPF) updates iptables/BPF rules → no more traffic to that IP
6. The failing pod's IP is gone from the load balancer pool — users don't see errors

This is why readiness probes are the correct mechanism for "don't send me traffic while I'm warming up" — it's a clean, automatic, Kubernetes-native mechanism.

---

### Q5. A deployment rollout is stuck. How do you investigate and fix it?

**Deep dive.**

```bash
# Check rollout status
kubectl rollout status deployment/payment-service

# Output if stuck:
# Waiting for deployment "payment-service" rollout to finish: 1 out of 3 new replicas have been updated...

# Why is it stuck? Check the new pods:
kubectl get pods -l app=payment-service
# Shows: 1 Running, 1 Pending, 1 CrashLoopBackOff

# The new pod is failing. The rolling update won't proceed (maxUnavailable: 1).
# Diagnose the failing pod (see Q1 above), then either:

# FIX A: Fix the bug, push a new image, update the deployment
kubectl set image deployment/payment-service app=registry.co/app:fixed-sha

# FIX B: Rollback to the last known-good version
kubectl rollout undo deployment/payment-service

# Verify rollback
kubectl rollout status deployment/payment-service
kubectl rollout history deployment/payment-service
```

**The architectural lesson:** The rolling update got stuck because of the `maxUnavailable: 1` setting — Kubernetes won't remove healthy old pods until the new pod is healthy. This IS the correct behavior. It's self-protective. The fix is to fix the new image, not to bypass the safety mechanism.

---

## Part 2 — Knowledge Check

**Q: What does `kubectl get pods` show vs `kubectl describe pod`?**
A: `get pods` shows a brief status table (NAME, READY, STATUS, RESTARTS, AGE). `describe pod` shows full details: events, probe status, resource limits, volume mounts, conditions. Use `describe` for debugging.

**Q: What is the difference between `imagePullPolicy: Always` and `IfNotPresent`?**
A: `Always` pulls the image from registry on every pod start (slow but ensures latest). `IfNotPresent` uses cached image if available (fast, but might use stale image). In production, pin images to SHA — then `IfNotPresent` is safe because the SHA uniquely identifies the image.

**Q: What are resource `requests` vs `limits`? What happens when a container exceeds its memory limit?**
A: Requests = what the scheduler uses for placement (guaranteed). Limits = maximum allowed. Exceeding CPU limit → container is CPU-throttled (slows, not killed). Exceeding memory limit → container is OOMKilled (SIGKILL, instant death). This is why memory limits must be set with headroom — a tight limit causes random OOMKills under load.

---

## Part 3 — Senior Gotchas

| Trap | What juniors say | What seniors say |
|---|---|---|
| "The pod keeps restarting" | Re-deploy | `kubectl logs --previous` to read crash logs before debugging |
| "K8s is slow" | Add more replicas | Check resource requests vs actual usage. Probably CPU-throttled at limit |
| "My service is down" | Restart the pods | Check if readiness probe is failing — no need to restart if pods are UP but not ready |
| "I'll just use `latest` tag" | It's the newest version | `latest` is non-deterministic in K8s — different nodes may pull different images |
| "Kubernetes handles everything" | Set replicas=1, no resource limits | HA requires minReplicas≥2, PodDisruptionBudget, topologySpreadConstraints |
| "I'll SSH into the pod to fix it" | `kubectl exec -it pod -- bash` then make changes | Containers are immutable. Any change is lost on restart. Fix the Dockerfile or config. |
