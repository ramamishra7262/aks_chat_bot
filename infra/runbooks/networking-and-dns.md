# Diagnosing Networking and DNS Issues in AKS

## Symptoms
Services are unreachable, DNS resolution fails inside pods, or ingress returns 502/504.

## Triage steps
1. `get_services` - confirm the Service exists, has the expected selector, and has
   endpoints (a Service with no matching pods has no endpoints).
2. `get_pods` with the Service's label selector - confirm at least one pod is
   `Running` and `Ready`.
3. `get_events` - look for `FailedToUpdateEndpoint`, `NetworkPolicy`, or CoreDNS
   related warnings.
4. Check CoreDNS pods in `kube-system` with `get_pods` and `get_pod_logs` for
   resolution errors (`SERVFAIL`, `i/o timeout`).

## Common root causes and fixes
- **Selector mismatch**: The Service `selector` doesn't match pod labels - recreate
  the Service with `create_service` using the correct selector.
- **NetworkPolicy blocking traffic**: A deny-by-default NetworkPolicy may be blocking
  ingress/egress between namespaces. Review policies and create a permissive policy
  for the required traffic if appropriate.
- **CoreDNS CPU throttling / crash**: Restart CoreDNS with `restart_deployment` in
  `kube-system`, and check `get_nodes` for node pressure.
- **Ingress 502/504**: The backend Service has no healthy endpoints - trace back to
  pod readiness probes failing (see crashloopbackoff.md).
