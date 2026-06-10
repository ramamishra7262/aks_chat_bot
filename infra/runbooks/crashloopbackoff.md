# Diagnosing CrashLoopBackOff

## Symptoms
A pod repeatedly restarts and shows status `CrashLoopBackOff` in `kubectl get pods`.

## Triage steps
1. Run `describe_pod` to check container exit codes and the `waiting`/`terminated` reason.
2. Run `get_pod_logs` with `previous: true` to see logs from the crashed container instance.
3. Check `get_events` for the namespace - look for `OOMKilled`, `Failed`, or `BackOff` events.

## Common root causes and fixes
- **Exit code 1 (application error)**: Check application logs for stack traces or missing
  environment variables/config. Fix the underlying config (e.g. via create_configmap or
  create_secret) and restart the deployment with restart_deployment.
- **Exit code 137 (OOMKilled)**: The container exceeded its memory limit. Increase the
  memory limit in the Deployment spec, or scale horizontally with scale_deployment to
  reduce per-pod load.
- **Exit code 143 (SIGTERM)**: Often caused by a failing readiness/liveness probe or a
  slow graceful shutdown. Review probe configuration and increase
  `terminationGracePeriodSeconds` if needed.
- **ImagePullBackOff**: Verify the image name/tag and registry credentials (imagePullSecrets).

## Recommended remediation order
1. Fix root cause (config, image, resource limits).
2. `restart_deployment` to roll out the fix.
3. `check_pod_health` to confirm the namespace is healthy again.
