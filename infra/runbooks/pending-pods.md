# Diagnosing Pods Stuck in Pending

## Symptoms
A pod remains in `Pending` phase and never schedules onto a node.

## Triage steps
1. Run `get_events` filtered to the pod - look for `FailedScheduling` events.
2. Run `get_nodes` to check node readiness, capacity and allocatable resources.
3. Run `describe_pod` to inspect resource requests, node selectors, tolerations, and
   affinity rules.

## Common root causes and fixes
- **Insufficient CPU/memory on nodes**: Either reduce the pod's resource requests or
  scale the AKS node pool (this requires the AKS Terraform pipeline - the chatbot can
  surface the recommendation but cannot resize node pools directly).
- **Node selector / affinity mismatch**: The pod's `nodeSelector` or
  `affinity.nodeAffinity` does not match any node's labels. Update the manifest
  (re-create the object with corrected selectors) or remove the constraint.
- **PVC not bound**: If the pod mounts a PersistentVolumeClaim that is `Pending`, check
  the StorageClass and ensure the underlying Azure Disk/Files quota is not exhausted.
- **Taints without matching tolerations**: Add the required `tolerations` to the pod
  spec, or schedule onto a different node pool.
