#!/usr/bin/env python3
"""
Defense Unicorns & Kubernetes Interactive CLI Troubleshooting Drill Manager
Injects, verifies, teaches, and heals cluster, Zarf, UDS, and Lula compliance failures.
"""

import argparse
import json
import random
import sys
from typing import Any

from common import (
    BLUE,
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    REPO_ROOT,
    RESET,
    YELLOW,
    detect_training_namespace,
    run_cmd,
)

MYSTERY_STATE_FILE = REPO_ROOT / ".active_mystery_drill.json"


def build_scenarios(ns: str) -> dict[str, dict[str, Any]]:
    """Build the scenario catalog parameterized by the active training namespace."""
    return {
        # ======================================================================
        # DOMAIN 1: ZARF & AIR-GAP REGISTRY
        # ======================================================================
        "zarf-untracked-image": {
            "domain": "Zarf/Air-Gap",
            "tools": ["kubectl", "zarf"],
            "title": "Unseeded Container Image Tag in Air-Gap (ImagePullBackOff)",
            "description": (
                f"Patches order-api in '{ns}' to request an image tag ('python:3.11-unseeded-airgap') "
                "that was never packaged into the internal Zarf registry."
            ),
            "inject_cmds": [
                f"kubectl set image deployment/order-api order-api=python:3.11-unseeded-airgap -n {ns}"
            ],
            "heal_cmds": [
                f"kubectl set image deployment/order-api order-api=python:3.11-alpine -n {ns}"
            ],
            "verify_cmd": f"kubectl get pods -n {ns} -l app=order-api",
            "symptoms": (
                "New order-api replica is stuck in ErrImagePull / ImagePullBackOff because the internal "
                "Zarf registry (127.0.0.1:31999) does not have the requested tag and WAN egress is blocked."
            ),
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Spot the Failing Pod)",
                    "prompt": f"Check pod statuses in the '{ns}' namespace to see which workload is failing.",
                    "recommended_cmd": f"kubectl get pods -n {ns} -o wide",
                    "hint": f"Run `kubectl get pods -n {ns} -o wide` and look for ErrImagePull or ImagePullBackOff.",
                    "explanation": (
                        "Notice that an order-api pod is stuck in `ErrImagePull` or `ImagePullBackOff` while "
                        "attempting to roll out."
                    ),
                },
                {
                    "phase": "Phase 2: Isolate (Inspect Kubelet Image Pull Events)",
                    "prompt": "Inspect the pod events on order-api to see the exact image URL and registry error.",
                    "recommended_cmd": f"kubectl describe pod -n {ns} -l app=order-api | tail -n 25",
                    "hint": f"Use `kubectl describe pod -n {ns} -l app=order-api` to view the Events table at the bottom.",
                    "explanation": (
                        "Look at the `Failed to pull image` event: Zarf's mutating webhook rewrote the image to "
                        "the internal Zarf seed registry (`127.0.0.1:31999/...`), but the tag `3.11-unseeded-airgap` "
                        "returns `manifest unknown`."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Query Internal Zarf Registry Catalog)",
                    "prompt": "Use the Zarf CLI to list what repositories and tags actually exist inside the in-cluster registry.",
                    "recommended_cmd": "zarf tools registry catalog",
                    "hint": "Run `zarf tools registry catalog` (and `zarf tools registry ls library/python`) to inspect seeded images.",
                    "explanation": (
                        "`zarf tools registry catalog` queries the internal registry directly without needing external tools. "
                        "Only `python:3.11-alpine` was packaged in the Zarf bundle—`3.11-unseeded-airgap` does not exist."
                    ),
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Restore Seeded Image Tag)",
                    "prompt": f"Revert order-api in '{ns}' back to the valid seeded image `python:3.11-alpine` (or roll back the deployment).",
                    "recommended_cmd": f"kubectl set image deployment/order-api order-api=python:3.11-alpine -n {ns}",
                    "hint": f"Run `kubectl set image deployment/order-api order-api=python:3.11-alpine -n {ns}` or `kubectl rollout undo deployment/order-api -n {ns}`.",
                    "explanation": (
                        "Updating the image tag back to `python:3.11-alpine` allows Zarf's mutating webhook to match "
                        "the seeded image digest in the local registry."
                    ),
                },
            ],
        },
        "zarf-webhook-bypass": {
            "domain": "Zarf/Air-Gap",
            "tools": ["kubectl", "zarf"],
            "title": "Zarf Mutating Webhook Bypassed (zarf.dev/agent=ignore)",
            "description": (
                f"Adds the label `zarf.dev/agent: ignore` to queue-worker pod template in '{ns}' "
                "and sets `imagePullPolicy: Always`, causing kubelet to bypass the internal Zarf registry "
                "and attempt an upstream internet pull across the air-gap."
            ),
            "inject_cmds": [
                f"""kubectl patch deployment queue-worker -n {ns} --type='json' -p='[
                    {{"op":"add","path":"/spec/template/metadata/labels/zarf.dev~1agent","value":"ignore"}},
                    {{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Always"}}
                ]'"""
            ],
            "heal_cmds": [
                f"""kubectl patch deployment queue-worker -n {ns} --type='json' -p='[
                    {{"op":"remove","path":"/spec/template/metadata/labels/zarf.dev~1agent"}},
                    {{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}}
                ]' 2>/dev/null || kubectl rollout undo deployment/queue-worker -n {ns}"""
            ],
            "verify_cmd": f"kubectl get pods -n {ns} -l app=queue-worker",
            "symptoms": (
                "queue-worker fails with ImagePullBackOff trying to reach registry-1.docker.io instead of "
                "127.0.0.1:31999 because the Zarf agent webhook ignored the pod."
            ),
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Check Pod & Zarf Agent Logs)",
                    "prompt": f"Check the pod status in '{ns}' and inspect recent events.",
                    "recommended_cmd": f"kubectl get pods -n {ns} -l app=queue-worker",
                    "hint": f"Run `kubectl get pods -n {ns} -l app=queue-worker`.",
                    "explanation": "The newly created `queue-worker` pod is stuck in `ErrImagePull` / `ImagePullBackOff`.",
                },
                {
                    "phase": "Phase 2: Isolate (Compare Image URL & Zarf Webhook Logs)",
                    "prompt": "Check the Zarf agent mutating webhook logs in the `zarf` namespace or describe the failing pod.",
                    "recommended_cmd": f"kubectl describe pod -n {ns} -l app=queue-worker | grep -E 'Image:|Failed|zarf'",
                    "hint": f"Run `kubectl describe pod -n {ns} -l app=queue-worker` and check `kubectl logs -n zarf -l app=agent-hook --tail=20`.",
                    "explanation": (
                        "Notice the pod is attempting to pull `docker.io/library/python:3.11-alpine` directly from the internet "
                        "rather than `127.0.0.1:31999/...`!"
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Inspect Pod Template Labels)",
                    "prompt": f"Inspect the labels on the `queue-worker` deployment template in '{ns}'.",
                    "recommended_cmd": f"kubectl get deployment queue-worker -n {ns} -o jsonpath='{{.spec.template.metadata.labels}}'",
                    "hint": f"Run `kubectl get deployment queue-worker -n {ns} -o jsonpath='{{.spec.template.metadata.labels}}'`.",
                    "explanation": (
                        "The pod template has `\"zarf.dev/agent\":\"ignore\"`, which explicitly instructs Zarf's mutating "
                        "admission webhook not to rewrite image references or inject registry pull secrets."
                    ),
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Re-enable Zarf Agent Mutation)",
                    "prompt": "Roll back or patch the `queue-worker` deployment to remove `zarf.dev/agent: ignore`.",
                    "recommended_cmd": f"kubectl rollout undo deployment/queue-worker -n {ns}",
                    "hint": f"Run `kubectl rollout undo deployment/queue-worker -n {ns}`.",
                    "explanation": (
                        "Removing the `zarf.dev/agent: ignore` label allows Zarf's webhook to mutate the pod spec back "
                        "to the in-cluster registry."
                    ),
                },
            ],
        },
        # ======================================================================
        # DOMAIN 2: UDS BUNDLE & KUBERNETES NETWORKING
        # ======================================================================
        "net-policy-block": {
            "domain": "UDS/Networking",
            "tools": ["kubectl", "uds"],
            "title": "Zero-Trust NetworkPolicy Ingress Block",
            "description": (
                f"Applies an overriding NetworkPolicy ('deny-order-api-ingress') in '{ns}' that selects "
                "`app: order-api` and blocks all ingress traffic from `frontend`."
            ),
            "inject_cmds": [
                f"""cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-order-api-ingress
  namespace: {ns}
spec:
  podSelector:
    matchLabels:
      app: order-api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: nonexistent-service
EOF"""
            ],
            "heal_cmds": [
                f"kubectl delete networkpolicy deny-order-api-ingress -n {ns} --ignore-not-found"
            ],
            "verify_cmd": f"kubectl get networkpolicy -n {ns}",
            "symptoms": (
                "All pods show 1/1 Running, but requests from frontend to order-api:8080 time out "
                "due to a restrictive NetworkPolicy."
            ),
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Pods Running, Traffic Timing Out)",
                    "prompt": f"Verify that pods and services in '{ns}' appear healthy despite the connectivity failure.",
                    "recommended_cmd": f"kubectl get pods,svc -n {ns}",
                    "hint": f"Run `kubectl get pods,svc -n {ns}`.",
                    "explanation": "Both `frontend` and `order-api` pods are `Running` and Services have valid ClusterIPs.",
                },
                {
                    "phase": "Phase 2: Isolate (List Active NetworkPolicies)",
                    "prompt": f"List the Kubernetes NetworkPolicies active in the '{ns}' namespace.",
                    "recommended_cmd": f"kubectl get networkpolicy -n {ns}",
                    "hint": f"Run `kubectl get netpol -n {ns}`.",
                    "explanation": (
                        "Alongside `allow-training-internal`, there is a suspicious policy named `deny-order-api-ingress` "
                        "targeting `app=order-api`."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Inspect NetworkPolicy Rules)",
                    "prompt": "Describe `deny-order-api-ingress` to see which pods are allowed to connect to `order-api`.",
                    "recommended_cmd": f"kubectl describe networkpolicy deny-order-api-ingress -n {ns}",
                    "hint": f"Run `kubectl describe netpol deny-order-api-ingress -n {ns}`.",
                    "explanation": (
                        "The policy restricts ingress on `app=order-api` exclusivamente to `app=nonexistent-service`, "
                        "dropping packets from `frontend`."
                    ),
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Remove Rogue NetworkPolicy)",
                    "prompt": f"Delete the rogue `deny-order-api-ingress` NetworkPolicy in '{ns}'.",
                    "recommended_cmd": f"kubectl delete networkpolicy deny-order-api-ingress -n {ns}",
                    "hint": f"Run `kubectl delete netpol deny-order-api-ingress -n {ns}`.",
                    "explanation": "Deleting the rogue policy restores inter-service communication under `allow-training-internal`.",
                },
            ],
        },
        "net-port-mismatch": {
            "domain": "UDS/Networking",
            "tools": ["kubectl"],
            "title": "Service TargetPort Misconfiguration (Connection Refused)",
            "description": f"Changes `order-api` Service targetPort in '{ns}' from 8080 to 9090.",
            "inject_cmds": [
                f"""kubectl patch svc order-api -n {ns} --type='json' -p='[{{"op":"replace","path":"/spec/ports/0/targetPort","value":9090}}]'"""
            ],
            "heal_cmds": [
                f"""kubectl patch svc order-api -n {ns} --type='json' -p='[{{"op":"replace","path":"/spec/ports/0/targetPort","value":8080}}]'"""
            ],
            "verify_cmd": f"kubectl get svc,ep order-api -n {ns}",
            "symptoms": (
                "order-api pods are 1/1 Running and DNS resolves, but connections to order-api:8080 "
                "immediately fail with 'Connection refused'."
            ),
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Inspect Service & Endpoints)",
                    "prompt": f"Check the `order-api` Service and Endpoints in '{ns}'.",
                    "recommended_cmd": f"kubectl get svc,ep order-api -n {ns}",
                    "hint": f"Run `kubectl get svc,ep order-api -n {ns}`.",
                    "explanation": (
                        "Look closely at the `ENDPOINTS` column: the pod IPs are listed with port `:9090` instead of `:8080`!"
                    ),
                },
                {
                    "phase": "Phase 2: Isolate (Compare Service TargetPort vs ContainerPort)",
                    "prompt": "Describe the `order-api` Service and check the container port on the `order-api` Deployment.",
                    "recommended_cmd": f"kubectl describe svc order-api -n {ns}",
                    "hint": f"Run `kubectl describe svc order-api -n {ns}`.",
                    "explanation": (
                        "`Port` is `8080/TCP`, but `TargetPort` was changed to `9090/TCP`, while the Python HTTP server "
                        "inside the container listens on port `8080`."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Verify Container Listening Port)",
                    "prompt": "Check the containerPort configured on the `order-api` deployment.",
                    "recommended_cmd": f"kubectl get deploy order-api -n {ns} -o jsonpath='{{.spec.template.spec.containers[0].ports}}'",
                    "hint": f"Run `kubectl get deploy order-api -n {ns} -o jsonpath='{{.spec.template.spec.containers[0].ports}}'`.",
                    "explanation": "The container exposes `containerPort: 8080`, confirming the Service `targetPort: 9090` is wrong.",
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Patch Service TargetPort to 8080)",
                    "prompt": f"Patch the `order-api` Service in '{ns}' so `targetPort` is `8080`.",
                    "recommended_cmd": f"kubectl patch svc order-api -n {ns} --type='json' -p='[{{\"op\":\"replace\",\"path\":\"/spec/ports/0/targetPort\",\"value\":8080}}]'",
                    "hint": f"Run `kubectl patch svc order-api -n {ns} -p '{{\"spec\":{{\"ports\":[{{\"port\":8080,\"targetPort\":8080}}]}}}}'`.",
                    "explanation": "Endpoints immediately update to `:8080` and traffic flows normally.",
                },
            ],
        },
        "net-service-endpoint": {
            "domain": "UDS/Networking",
            "tools": ["kubectl"],
            "title": "Service Selector Label Mismatch (Empty Endpoints)",
            "description": f"Changes `order-api` Service selector in '{ns}' to `app: order-api-wrong-label`.",
            "inject_cmds": [
                f"""kubectl patch svc order-api -n {ns} --type='json' -p='[{{"op":"replace","path":"/spec/selector/app","value":"order-api-wrong-label"}}]'"""
            ],
            "heal_cmds": [
                f"""kubectl patch svc order-api -n {ns} --type='json' -p='[{{"op":"replace","path":"/spec/selector/app","value":"order-api"}}]'"""
            ],
            "verify_cmd": f"kubectl get ep order-api -n {ns}",
            "symptoms": f"Service `order-api` has `<none>` in its Endpoints list (`kubectl get ep order-api -n {ns}`).",
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Check Service Endpoints)",
                    "prompt": f"Check the Endpoints object for `order-api` in '{ns}'.",
                    "recommended_cmd": f"kubectl get endpoints order-api -n {ns}",
                    "hint": f"Run `kubectl get ep order-api -n {ns}`.",
                    "explanation": "The `ENDPOINTS` column is `<none>`, meaning the Service has zero backing pods.",
                },
                {
                    "phase": "Phase 2: Isolate (Inspect Service Selector)",
                    "prompt": "Describe the `order-api` Service to see what pod labels its `Selector` is looking for.",
                    "recommended_cmd": f"kubectl describe svc order-api -n {ns}",
                    "hint": f"Run `kubectl describe svc order-api -n {ns}` and check the `Selector:` line.",
                    "explanation": "The Service selector is looking for `app=order-api-wrong-label`.",
                },
                {
                    "phase": "Phase 3: Root Cause (Compare Against Actual Pod Labels)",
                    "prompt": f"List the pods in '{ns}' with their labels displayed.",
                    "recommended_cmd": f"kubectl get pods -n {ns} --show-labels",
                    "hint": f"Run `kubectl get pods -n {ns} --show-labels`.",
                    "explanation": "The running pods have label `app=order-api`, not `app=order-api-wrong-label`.",
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Fix Service Selector)",
                    "prompt": f"Patch the `order-api` Service selector back to `app: order-api`.",
                    "recommended_cmd": f"kubectl patch svc order-api -n {ns} -p '{{\"spec\":{{\"selector\":{{\"app\":\"order-api\"}}}}}}'",
                    "hint": f"Run `kubectl patch svc order-api -n {ns} -p '{{\"spec\":{{\"selector\":{{\"app\":\"order-api\"}}}}}}'`.",
                    "explanation": "Kubernetes immediately repopulates the `Endpoints` slice with the running pod IPs.",
                },
            ],
        },
        # ======================================================================
        # DOMAIN 3: KUBERNETES COMPUTE & STORAGE
        # ======================================================================
        "comp-oom-killed": {
            "domain": "Compute",
            "tools": ["kubectl"],
            "title": "Out Of Memory CrashLoop (OOMKilled / Exit Code 137)",
            "description": f"Injects an unbounded memory allocation loop into `queue-worker` in '{ns}'.",
            "inject_cmds": [
                f"""cat << 'EOF' | kubectl patch deployment queue-worker -n {ns} --type='json' --patch-file /dev/stdin
[{{"op":"replace","path":"/spec/template/spec/containers/0/command","value":["/bin/sh","-c","python3 -c \\"import time; b=[]; print('Leaking memory...'); [b.append('X'*1024*1024) or time.sleep(0.05) for _ in range(500)]\\""]}}]
EOF"""
            ],
            "heal_cmds": [
                f"kubectl rollout undo deployment/queue-worker -n {ns}"
            ],
            "verify_cmd": f"kubectl get pods -n {ns} -l app=queue-worker",
            "symptoms": "queue-worker restarts repeatedly in CrashLoopBackOff with Last State: OOMKilled (Exit Code 137).",
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Identify Crashing Pod)",
                    "prompt": f"List all pods in '{ns}' to find the crashing workload.",
                    "recommended_cmd": f"kubectl get pods -n {ns}",
                    "hint": f"Run `kubectl get pods -n {ns}`.",
                    "explanation": "`queue-worker` has multiple restarts and is entering `OOMKilled` / `CrashLoopBackOff`.",
                },
                {
                    "phase": "Phase 2: Isolate (Check Container Exit Code & Last Termination State)",
                    "prompt": "Describe the `queue-worker` pod to inspect `Last State`, `Reason`, and `Exit Code`.",
                    "recommended_cmd": f"kubectl describe pod -n {ns} -l app=queue-worker | grep -A 12 'Last State:'",
                    "hint": f"Run `kubectl describe pod -n {ns} -l app=queue-worker`.",
                    "explanation": (
                        "`Reason: OOMKilled` and `Exit Code: 137` (SIGKILL = 128 + 9) prove the Linux kernel cgroup OOM killer "
                        "terminated the container for exceeding its 128Mi memory limit."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Inspect Previous Container Logs)",
                    "prompt": "Fetch logs from the previous crashed container instance of `queue-worker`.",
                    "recommended_cmd": f"kubectl logs -n {ns} -l app=queue-worker --previous",
                    "hint": f"Run `kubectl logs -n {ns} -l app=queue-worker --previous`.",
                    "explanation": "The logs show `Leaking memory...` right before the kernel killed the process.",
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Roll Back Deployment)",
                    "prompt": f"Roll back the `queue-worker` deployment in '{ns}' to its previous healthy revision.",
                    "recommended_cmd": f"kubectl rollout undo deployment/queue-worker -n {ns}",
                    "hint": f"Run `kubectl rollout undo deployment/queue-worker -n {ns}`.",
                    "explanation": "`kubectl rollout undo` restores the healthy worker loop and stabilizes memory usage.",
                },
            ],
        },
        "comp-probe-fail": {
            "domain": "Compute",
            "tools": ["kubectl"],
            "title": "Liveness Probe HTTP 404 Failure Loop",
            "description": f"Configures an invalid livenessProbe path (`/healthz-broken-path`) on `order-api` in '{ns}'.",
            "inject_cmds": [
                f"""kubectl patch deployment order-api -n {ns} --type='json' -p='[{{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/healthz-broken-path"}}]'"""
            ],
            "heal_cmds": [
                f"""kubectl patch deployment order-api -n {ns} --type='json' -p='[{{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/healthz"}}]'"""
            ],
            "verify_cmd": f"kubectl get events -n {ns} --sort-by=.metadata.creationTimestamp | tail -n 10",
            "symptoms": "order-api containers are repeatedly killed and restarted by kubelet due to HTTP 404 liveness probe failures.",
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Observe Pod Restarts)",
                    "prompt": f"Check pod statuses and restart counts in '{ns}'.",
                    "recommended_cmd": f"kubectl get pods -n {ns} -l app=order-api",
                    "hint": f"Run `kubectl get pods -n {ns} -l app=order-api`.",
                    "explanation": "`order-api` pods are restarting every ~30 seconds.",
                },
                {
                    "phase": "Phase 2: Isolate (Inspect Namespace Events)",
                    "prompt": f"Check recent Kubernetes events in '{ns}' sorted by creation timestamp.",
                    "recommended_cmd": f"kubectl get events -n {ns} --sort-by=.metadata.creationTimestamp | tail -n 15",
                    "hint": f"Run `kubectl get events -n {ns} --sort-by=.metadata.creationTimestamp`.",
                    "explanation": (
                        "Events show `Warning Unhealthy: Liveness probe failed: HTTP probe failed with statuscode: 404`."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Compare Liveness vs Readiness Probe Paths)",
                    "prompt": "Inspect the `livenessProbe` and `readinessProbe` definitions on `order-api`.",
                    "recommended_cmd": f"kubectl describe deploy order-api -n {ns} | grep -E 'Liveness:|Readiness:'",
                    "hint": f"Run `kubectl describe deploy order-api -n {ns}`.",
                    "explanation": (
                        "Readiness checks `/healthz` (200 OK), while Liveness was misconfigured to `/healthz-broken-path` (404)."
                    ),
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Fix Liveness Probe Path)",
                    "prompt": f"Patch the `order-api` livenessProbe path back to `/healthz`.",
                    "recommended_cmd": f"kubectl patch deployment order-api -n {ns} --type='json' -p='[{{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/livenessProbe/httpGet/path\",\"value\":\"/healthz\"}}]'",
                    "hint": f"Run `kubectl rollout undo deployment/order-api -n {ns}` or patch `/healthz`.",
                    "explanation": "Liveness probes now return HTTP 200 and pod restarts cease.",
                },
            ],
        },
        "comp-unschedulable": {
            "domain": "Compute",
            "tools": ["kubectl"],
            "title": "Unschedulable Pod / NodeSelector Mismatch",
            "description": f"Applies a non-existent `nodeSelector` (`topology.kubernetes.io/zone: non-existent-zone-c`) to `order-api` in '{ns}'.",
            "inject_cmds": [
                f"""kubectl patch deployment order-api -n {ns} --type='json' -p='[{{"op":"add","path":"/spec/template/spec/nodeSelector","value":{{"topology.kubernetes.io/zone":"non-existent-zone-c"}}}}]'"""
            ],
            "heal_cmds": [
                f"""kubectl patch deployment order-api -n {ns} --type='json' -p='[{{"op":"remove","path":"/spec/template/spec/nodeSelector"}}]'"""
            ],
            "verify_cmd": f"kubectl get pods -n {ns} -l app=order-api",
            "symptoms": "New order-api pods remain stuck in Pending state with a FailedScheduling event.",
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Spot Pending Pods)",
                    "prompt": f"Check pod statuses in '{ns}'.",
                    "recommended_cmd": f"kubectl get pods -n {ns} -o wide",
                    "hint": f"Run `kubectl get pods -n {ns} -o wide`.",
                    "explanation": "New `order-api` replica is stuck in `Pending` with `<none>` assigned for `NODE`.",
                },
                {
                    "phase": "Phase 2: Isolate (Check Scheduler Failure Event)",
                    "prompt": "Describe the pending `order-api` pod to see why `default-scheduler` rejected it.",
                    "recommended_cmd": f"kubectl describe pod -n {ns} -l app=order-api | tail -n 15",
                    "hint": f"Run `kubectl describe pod -n {ns} -l app=order-api`.",
                    "explanation": (
                        "`Warning FailedScheduling: 0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector`."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Compare Node Labels vs Pod NodeSelector)",
                    "prompt": "Check the labels on your cluster nodes and compare with the deployment's `nodeSelector`.",
                    "recommended_cmd": "kubectl get nodes --show-labels",
                    "hint": "Run `kubectl get nodes --show-labels`.",
                    "explanation": (
                        "The deployment requires `topology.kubernetes.io/zone=non-existent-zone-c`, which no node has."
                    ),
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Remove Invalid NodeSelector)",
                    "prompt": f"Remove the invalid `nodeSelector` from `order-api` in '{ns}'.",
                    "recommended_cmd": f"kubectl patch deployment order-api -n {ns} --type='json' -p='[{{\"op\":\"remove\",\"path\":\"/spec/template/spec/nodeSelector\"}}]'",
                    "hint": f"Run `kubectl patch deployment order-api -n {ns} --type='json' -p='[{{\"op\":\"remove\",\"path\":\"/spec/template/spec/nodeSelector\"}}]'`.",
                    "explanation": "The scheduler immediately binds the pod to the node.",
                },
            ],
        },
        "stor-pvc-pending": {
            "domain": "Storage",
            "tools": ["kubectl"],
            "title": "Unsatisfied StorageClass / Pending PVC",
            "description": f"Creates a PersistentVolumeClaim (`drill-pending-pvc`) in '{ns}' requesting a non-existent StorageClass.",
            "inject_cmds": [
                f"""cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: drill-pending-pvc
  namespace: {ns}
spec:
  accessModes: [ "ReadWriteOnce" ]
  storageClassName: non-existent-nvme-sc
  resources:
    requests:
      storage: 1Gi
EOF"""
            ],
            "heal_cmds": [
                f"kubectl delete pvc drill-pending-pvc -n {ns} --ignore-not-found"
            ],
            "verify_cmd": f"kubectl get pvc -n {ns}",
            "symptoms": "PersistentVolumeClaim `drill-pending-pvc` remains stuck in Pending state with ProvisioningFailed events.",
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Check PVC Status)",
                    "prompt": f"List PersistentVolumeClaims in '{ns}'.",
                    "recommended_cmd": f"kubectl get pvc -n {ns}",
                    "hint": f"Run `kubectl get pvc -n {ns}`.",
                    "explanation": "`drill-pending-pvc` is stuck in `Pending` requesting `STORAGECLASS: non-existent-nvme-sc`.",
                },
                {
                    "phase": "Phase 2: Isolate (Inspect PVC Events)",
                    "prompt": "Describe `drill-pending-pvc` to view the volume provisioner failure reason.",
                    "recommended_cmd": f"kubectl describe pvc drill-pending-pvc -n {ns}",
                    "hint": f"Run `kubectl describe pvc drill-pending-pvc -n {ns}`.",
                    "explanation": "`storageclass.storage.k8s.io \"non-existent-nvme-sc\" not found`.",
                },
                {
                    "phase": "Phase 3: Root Cause (List Available Cluster StorageClasses)",
                    "prompt": "List the actual StorageClasses installed in the cluster.",
                    "recommended_cmd": "kubectl get storageclass",
                    "hint": "Run `kubectl get sc`.",
                    "explanation": "K3s provides `local-path` as the default StorageClass, not `non-existent-nvme-sc`.",
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Delete Misconfigured PVC)",
                    "prompt": f"Delete the broken `drill-pending-pvc` claim in '{ns}'.",
                    "recommended_cmd": f"kubectl delete pvc drill-pending-pvc -n {ns}",
                    "hint": f"Run `kubectl delete pvc drill-pending-pvc -n {ns}`.",
                    "explanation": "Removing the invalid PVC clears the storage provisioning alert.",
                },
            ],
        },
        # ======================================================================
        # DOMAIN 4: LULA COMPLIANCE & SECURITY DRIFT
        # ======================================================================
        "sec-lula-drift": {
            "domain": "Lula/Security",
            "tools": ["lula", "kubectl"],
            "title": "DoD IL5 NIST 800-53 AC-3 Privilege Escalation Drift",
            "description": (
                f"Patches `order-api` in '{ns}' with `securityContext.allowPrivilegeEscalation: true`, "
                "causing live cluster drift that fails Lula OSCAL validation against `docs/compliance/oscal-il5.yaml`."
            ),
            "inject_cmds": [
                f"""kubectl patch deployment order-api -n {ns} --type='json' -p='[{{"op":"add","path":"/spec/template/spec/containers/0/securityContext","value":{{"allowPrivilegeEscalation":true}}}}]'"""
            ],
            "heal_cmds": [
                f"""kubectl patch deployment order-api -n {ns} --type='json' -p='[{{"op":"add","path":"/spec/template/spec/containers/0/securityContext","value":{{"allowPrivilegeEscalation":false}}}}]'"""
            ],
            "verify_cmd": "lula validate -f docs/compliance/oscal-il5.yaml -o docs/compliance/assessment-results.yaml",
            "symptoms": (
                "Pods run normally, but `lula validate -f docs/compliance/oscal-il5.yaml` fails control `ac-3` "
                "(UUID c65f7e81-d204-4cc6-93be-1706402f0ff8) with state `not-satisfied`."
            ),
            "tutor_steps": [
                {
                    "phase": "Phase 1: Detect (Run Lula OSCAL Compliance Validation)",
                    "prompt": "Run `lula validate` against `docs/compliance/oscal-il5.yaml` to audit the live cluster.",
                    "recommended_cmd": "lula validate -f docs/compliance/oscal-il5.yaml -o docs/compliance/assessment-results.yaml",
                    "hint": "Run `lula validate -f docs/compliance/oscal-il5.yaml -o docs/compliance/assessment-results.yaml`.",
                    "explanation": (
                        "Lula queries the Kubernetes API and evaluates the embedded OPA Rego policies, reporting "
                        "that control `ac-3` (`c65f7e81-d204-4cc6-93be-1706402f0ff8`) is `not-satisfied`!"
                    ),
                },
                {
                    "phase": "Phase 2: Isolate (Evaluate Assessment Results & Inspect OSCAL Rule)",
                    "prompt": "Run `lula evaluate` on the generated `docs/compliance/assessment-results.yaml` or inspect the failing Rego rule.",
                    "recommended_cmd": "lula evaluate -f docs/compliance/assessment-results.yaml",
                    "hint": "Run `lula evaluate -f docs/compliance/assessment-results.yaml` or inspect `docs/compliance/oscal-il5.yaml`.",
                    "explanation": (
                        "Control `ac-3` requires every container in `training-app` deployments to have "
                        "`securityContext.allowPrivilegeEscalation == false`."
                    ),
                },
                {
                    "phase": "Phase 3: Root Cause (Locate the Non-Compliant Deployment via kubectl)",
                    "prompt": f"Query deployments in '{ns}' to see which container has `allowPrivilegeEscalation: true`.",
                    "recommended_cmd": (
                        f"kubectl get deploy -n {ns} "
                        "-o jsonpath='{range .items[*]}{.metadata.name}{\": \"}{.spec.template.spec.containers[*].securityContext}{" + '"\\n"' + "}{end}'"
                    ),
                    "hint": f"Run `kubectl get deploy -n {ns} -o yaml | grep -B5 -A5 allowPrivilegeEscalation`.",
                    "explanation": "`order-api` has `{\"allowPrivilegeEscalation\":true}` in its container securityContext.",
                },
                {
                    "phase": "Phase 4: Remediate & Verify (Patch SecurityContext & Re-run Lula)",
                    "prompt": (
                        f"Patch `order-api` in '{ns}' back to `allowPrivilegeEscalation: false` and re-run `lula validate`."
                    ),
                    "recommended_cmd": (
                        f"kubectl patch deployment order-api -n {ns} --type='json' "
                        "-p='[{\"op\":\"add\",\"path\":\"/spec/template/spec/containers/0/securityContext\",\"value\":{\"allowPrivilegeEscalation\":false}}]' "
                        "&& lula validate -f docs/compliance/oscal-il5.yaml -o docs/compliance/assessment-results.yaml"
                    ),
                    "hint": "Patch `allowPrivilegeEscalation: false` on `order-api` and run `lula validate -f docs/compliance/oscal-il5.yaml`.",
                    "explanation": "All 5 NIST 800-53 controls now return `satisfied` in Lula!",
                },
            ],
        },
    }


def domain_badge(domain: str) -> str:
    colors = {
        "Zarf/Air-Gap": MAGENTA,
        "UDS/Networking": GREEN,
        "Compute": YELLOW,
        "Storage": BLUE,
        "Lula/Security": CYAN,
    }
    color = colors.get(domain, BLUE)
    return f"{color}{domain:<15}{RESET}"


def list_drills(scenarios: dict[str, dict[str, Any]]) -> None:
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}     DEFENSE UNICORNS & KUBERNETES CLI TROUBLESHOOTING DRILL CATALOG                {RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}\n")
    print(f"{BOLD}{'DOMAIN':<15} {'SCENARIO ID':<24} {'CLI TOOLS':<16} {'TITLE'}{RESET}")
    print(f"{'-' * 84}")
    for sc_id, data in scenarios.items():
        tools_str = ", ".join(data["tools"])
        print(f"{domain_badge(data['domain'])} {BOLD}{sc_id:<24}{RESET} {CYAN}{tools_str:<16}{RESET} {data['title']}")
        print(f"                {DIM}Symptoms: {data['symptoms']}{RESET}\n")

    print(f"{BOLD}Interactive Learning & Chaos Commands:{RESET}")
    print(f"  {BOLD}make drill-tutor SCENARIO=<id>{RESET}   -> Step-by-step interactive CLI tutor for a scenario")
    print(f"  {BOLD}make drill-mystery{RESET}               -> Inject a random blind fault to diagnose from scratch")
    print(f"  {BOLD}make drill-check{RESET}                 -> Audit cluster & Lula compliance health (solves mystery)")
    print(f"  {BOLD}make drill-inject SCENARIO=<id>{RESET}  -> Inject specific defect")
    print(f"  {BOLD}make drill-verify SCENARIO=<id>{RESET}  -> Observe live symptoms")
    print(f"  {BOLD}make drill-heal SCENARIO=<id|all>{RESET}-> Restore cluster to healthy state")
    print(f"  {BOLD}make drill-cheatsheet{RESET}            -> Print CLI diagnostic reference card\n")


def print_cheatsheet(ns: str) -> None:
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}     AIR-GAPPED PLATFORM ENGINEERING CLI TROUBLESHOOTING CHEAT SHEET                {RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}\n")
    sections = [
        (
            "1. KUBERNETES WORKLOAD & NETWORK DIAGNOSTICS (kubectl)",
            [
                (f"kubectl get pods -n {ns} -o wide", "Check pod status, restarts, IPs, and assigned nodes"),
                (f"kubectl get events -n {ns} --sort-by=.metadata.creationTimestamp", "Chronological namespace events (probe fails, pull errors)"),
                (f"kubectl describe pod -n {ns} -l app=order-api", "Inspect container exit codes (137=OOM), probes, and events"),
                (f"kubectl logs -n {ns} -l app=queue-worker --previous", "View stdout/stderr from a previously crashed container"),
                (f"kubectl get svc,ep,netpol -n {ns}", "Inspect Services, backing Endpoint IPs/ports, and NetworkPolicies"),
                (f"kubectl rollout undo deployment/<name> -n {ns}", "Roll back a broken Deployment to its previous revision"),
            ],
        ),
        (
            "2. ZARF AIR-GAP REGISTRY & WEBHOOK DIAGNOSTICS (zarf)",
            [
                ("zarf tools registry catalog", "List all container repositories inside the in-cluster Zarf registry"),
                ("zarf tools registry ls library/python", "List available tags for an image in the internal Zarf registry"),
                ("zarf package list", "List all Zarf packages deployed in the cluster"),
                ("zarf package inspect <pkg.tar.zst>", "Inspect components, images, and SBOMs inside a Zarf archive"),
                ("kubectl logs -n zarf -l app=agent-hook --tail=30", "Inspect Zarf mutating webhook pod mutation logs"),
            ],
        ),
        (
            "3. UDS BUNDLE & PEPR POLICY DIAGNOSTICS (uds)",
            [
                ("uds inspect build/uds-bundle-*.tar.zst", "Inspect UDS bundle manifest and constituent Zarf packages"),
                ("uds deploy build/uds-bundle-*.tar.zst --confirm", "Deploy a compiled UDS bundle across the air-gap"),
                ("uds monitor", "Stream real-time UDS Pepr policy admission & network events"),
            ],
        ),
        (
            "4. LULA OSCAL COMPLIANCE-AS-CODE DIAGNOSTICS (lula)",
            [
                ("lula validate -f docs/compliance/oscal-il5.yaml -o docs/compliance/assessment-results.yaml", "Evaluate live cluster state against NIST 800-53 OSCAL controls"),
                ("lula evaluate -f docs/compliance/assessment-results.yaml", "Gate pass/fail status on generated OSCAL assessment results"),
            ],
        ),
    ]
    for header, rows in sections:
        print(f"{BOLD}{YELLOW}{header}{RESET}")
        for cmd, desc in rows:
            print(f"  {GREEN}{cmd:<68}{RESET} {DIM}# {desc}{RESET}")
        print()


def pause_argocd_sync() -> None:
    """Temporarily pause ArgoCD automated sync if present so injected faults persist."""
    run_cmd(
        "kubectl patch application root-application -n argocd --type='merge' -p='{\"spec\":{\"syncPolicy\":null}}' 2>/dev/null || true",
        check=False,
        capture=True,
    )


def resume_argocd_sync() -> None:
    """Re-enable ArgoCD automated sync if present."""
    run_cmd(
        "kubectl patch application root-application -n argocd --type='merge' -p='{\"spec\":{\"syncPolicy\":{\"automated\":{\"prune\":true,\"selfHeal\":true}}}}' 2>/dev/null || true",
        check=False,
        capture=True,
    )


def inject_drill(sc_id: str, scenarios: dict[str, dict[str, Any]], quiet: bool = False) -> bool:
    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'. Run --list for options.{RESET}")
        return False
    scenario = scenarios[sc_id]
    if not quiet:
        print(f"\n{BOLD}{YELLOW}>>> Injecting Failure Scenario: {sc_id} ({scenario['title']}){RESET}")

    pause_argocd_sync()

    all_success = True
    for cmd in scenario["inject_cmds"]:
        res = run_cmd(cmd)
        if res.returncode != 0:
            if not quiet and res.stderr:
                print(f"{YELLOW}Warning executing injection: {res.stderr.strip()}{RESET}")
            all_success = False

    if all_success and not quiet:
        print(f"{GREEN}✓ Scenario '{sc_id}' successfully injected!{RESET}")
        print(f"{BOLD}Symptoms:{RESET} {scenario['symptoms']}")
        print(f"{BOLD}Tools to Practice:{RESET} {', '.join(scenario['tools'])}")
        print(f"Run {BOLD}make drill-tutor SCENARIO={sc_id} NO_INJECT=1{RESET} for guided CLI walk-through.\n")
    elif not all_success and not quiet:
        print(f"{RED}✗ Scenario '{sc_id}' injection encountered errors (is the cluster reachable?).{RESET}\n")
    return all_success


def heal_drill_single(sc_id: str, scenarios: dict[str, dict[str, Any]]) -> bool:
    scenario = scenarios[sc_id]
    print(f"{BLUE}Healing Scenario: {sc_id} ({scenario['title']})...{RESET}")
    all_success = True
    for cmd in scenario["heal_cmds"]:
        res = run_cmd(cmd)
        if res.returncode != 0:
            all_success = False
    if all_success:
        print(f"{GREEN}✓ Scenario '{sc_id}' healed.{RESET}")
    else:
        print(f"{RED}✗ Failed to heal Scenario '{sc_id}'.{RESET}")
    return all_success


def heal_drill(sc_id: str, scenarios: dict[str, dict[str, Any]]) -> bool:
    if sc_id == "all":
        print(f"\n{BOLD}{GREEN}>>> Healing all drill scenarios...{RESET}")
        has_error = False
        for s_id in scenarios:
            if not heal_drill_single(s_id, scenarios):
                has_error = True
        resume_argocd_sync()
        if MYSTERY_STATE_FILE.exists():
            MYSTERY_STATE_FILE.unlink()
        return not has_error

    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'.{RESET}")
        return False

    ok = heal_drill_single(sc_id, scenarios)
    resume_argocd_sync()
    if MYSTERY_STATE_FILE.exists():
        try:
            state = json.loads(MYSTERY_STATE_FILE.read_text())
            if state.get("scenario_id") == sc_id:
                MYSTERY_STATE_FILE.unlink()
        except Exception:
            pass
    return ok


def verify_drill(sc_id: str, scenarios: dict[str, dict[str, Any]], ns: str) -> None:
    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'.{RESET}")
        sys.exit(1)
    scenario = scenarios[sc_id]
    print(f"\n{BOLD}{BLUE}=== Diagnostic Status for Scenario: {sc_id} ==={RESET}")
    print(f"{BOLD}Expected Symptoms:{RESET} {scenario['symptoms']}\n")

    print(f"{BOLD}1. Scenario-Specific Check (`{scenario['verify_cmd']}`):{RESET}")
    v_res = run_cmd(scenario["verify_cmd"])
    print((v_res.stdout or "") + (v_res.stderr or ""))

    print(f"{BOLD}2. Active Pods in '{ns}' namespace:{RESET}")
    res = run_cmd(f"kubectl get pods -n {ns} -o wide")
    print(res.stdout if res.stdout else res.stderr)

    print(f"\n{BOLD}3. Recent Events in '{ns}' namespace:{RESET}")
    events_res = run_cmd(f"kubectl get events -n {ns} --sort-by=.metadata.creationTimestamp | tail -n 10")
    print(events_res.stdout if events_res.stdout else events_res.stderr)


def run_tutor(sc_id: str, scenarios: dict[str, dict[str, Any]], inject_first: bool = True) -> None:
    """Interactive 4-Phase CLI Tutor walking the user through real diagnostic commands."""
    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'. Run --list for options.{RESET}")
        sys.exit(1)

    scenario = scenarios[sc_id]
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}  INTERACTIVE CLI TROUBLESHOOTING TUTOR: {sc_id}{RESET}")
    print(f"{BOLD}{BLUE}  {scenario['title']} [{scenario['domain']}]{RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}")

    if inject_first:
        inject_drill(sc_id, scenarios, quiet=False)

    print(f"{BOLD}{YELLOW}INCIDENT TICKET:{RESET} {scenario['symptoms']}")
    print(f"{BOLD}{CYAN}CLI Tools Involved:{RESET} {', '.join(scenario['tools'])}")
    print(
        f"{DIM}Commands at any prompt: type a shell command to run it, or type "
        f"'hint' (show command), 'run' (auto-run recommended command), 'next' (skip step), "
        f"'heal' (fix & exit), or 'quit'.{RESET}\n"
    )

    steps = scenario.get("tutor_steps", [])
    for idx, step in enumerate(steps, start=1):
        print(f"{BOLD}{MAGENTA}--- [{idx}/{len(steps)}] {step['phase']} ---{RESET}")
        print(f"{BOLD}Task:{RESET} {step['prompt']}")

        while True:
            try:
                user_input = input(f"\n{BOLD}{GREEN}tutor ({sc_id}) [{idx}/{len(steps)}]> {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Exiting tutor. Run `make drill-heal SCENARIO={sc_id}` to restore cluster.{RESET}")
                return

            if not user_input:
                continue

            low = user_input.lower()
            if low in ("quit", "exit", "q"):
                print(f"{YELLOW}Exiting tutor. Run `make drill-heal SCENARIO={sc_id}` if the fault is still active.{RESET}")
                return
            if low == "heal":
                heal_drill(sc_id, scenarios)
                return
            if low in ("next", "skip", "n"):
                break
            if low in ("hint", "h", "?"):
                print(f"  {YELLOW}💡 Hint:{RESET} {step['hint']}")
                print(f"  {CYAN}Recommended Command:{RESET} {BOLD}{step['recommended_cmd']}{RESET}")
                continue
            if low == "explain":
                print(f"  {BLUE}📘 What to look for:{RESET} {step['explanation']}")
                continue

            cmd_to_run = step["recommended_cmd"] if low == "run" else user_input
            if low == "run":
                print(f"  {DIM}$ {cmd_to_run}{RESET}")

            res = run_cmd(cmd_to_run)
            if res.stdout:
                print(res.stdout.rstrip())
            if res.stderr:
                print(f"{YELLOW}{res.stderr.rstrip()}{RESET}")

            print(f"\n  {BLUE}📘 Takeaway:{RESET} {step['explanation']}")
            cont = input(f"  {DIM}Press Enter to advance to the next phase (or type 'retry' to run another command): {RESET}").strip().lower()
            if cont != "retry":
                break
        print()

    print(f"{BOLD}{GREEN}🎉 Completed all 4 diagnostic phases for '{sc_id}'!{RESET}")
    try:
        cleanup = input(f"Run automated heal check for '{sc_id}' now? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        cleanup = "n"
    if cleanup in ("", "y", "yes"):
        heal_drill(sc_id, scenarios)


def inject_mystery(scenarios: dict[str, dict[str, Any]]) -> None:
    """Pick a random scenario, inject it silently, and challenge the operator to diagnose & fix it."""
    sc_id = random.choice(list(scenarios.keys()))
    scenario = scenarios[sc_id]

    print(f"\n{BOLD}{MAGENTA}===================================================================================={RESET}")
    print(f"{BOLD}{MAGENTA}  🕵️  BLIND CHAOS INJECTION (MYSTERY TROUBLESHOOTING MODE)                           {RESET}")
    print(f"{BOLD}{MAGENTA}===================================================================================={RESET}\n")
    print("Injecting a random cluster, Zarf, UDS, or Lula compliance anomaly into the environment...")

    ok = inject_drill(sc_id, scenarios, quiet=True)
    MYSTERY_STATE_FILE.write_text(
        json.dumps({"scenario_id": sc_id, "domain": scenario["domain"], "title": scenario["title"]}, indent=2)
    )

    if ok:
        print(f"{GREEN}✓ Mystery fault injected!{RESET}\n")
    else:
        print(f"{YELLOW}⚠️ Mystery fault injection returned non-zero (cluster may be offline or unreachable).{RESET}\n")

    print(f"{BOLD}Your Mission:{RESET}")
    print("  1. Use `kubectl`, `zarf`, `uds`, and `lula` to detect, isolate, and remediate the issue.")
    print("  2. Need a CLI refresher? Run:  `make drill-cheatsheet`")
    print("  3. Ready to test your fix? Run: `make drill-check`")
    print("  4. Stuck? Reveal the fault via: `make drill-check REVEAL=1` or reset via `make drill-heal SCENARIO=all`\n")


def check_cluster_health(scenarios: dict[str, dict[str, Any]], ns: str, reveal: bool = False) -> bool:
    """Audit live cluster workloads, services, PVCs, and Lula compliance to verify remediation."""
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}  CLUSTER & LULA COMPLIANCE HEALTH AUDIT (Namespace: {ns})                          {RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}\n")

    if MYSTERY_STATE_FILE.exists():
        state = json.loads(MYSTERY_STATE_FILE.read_text())
        if reveal:
            sc_id = state["scenario_id"]
            print(f"{YELLOW}🔎 Active Mystery Scenario:{RESET} {BOLD}{sc_id}{RESET} — {state['title']} [{state['domain']}]")
            print(f"   Symptoms: {scenarios[sc_id]['symptoms']}\n")
        else:
            print(f"{MAGENTA}🕵️  A Mystery Drill is currently active (pass --reveal to see which one).{RESET}\n")

    checks_passed = True

    # 1. Check Pods in training namespace
    print(f"{BOLD}[1/4] Checking Pod Readiness in '{ns}'...{RESET}")
    pod_res = run_cmd(f"kubectl get pods -n {ns} --no-headers 2>/dev/null")
    if pod_res.returncode != 0 or not pod_res.stdout.strip():
        print(f"  {RED}✗ Unable to list pods in '{ns}' (or namespace is empty).{RESET}")
        checks_passed = False
    else:
        bad_pods = []
        for line in pod_res.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 3:
                name, ready, status = parts[0], parts[1], parts[2]
                if status == "Terminating":
                    continue
                if status != "Running" or ready.split("/")[0] != ready.split("/")[1]:
                    bad_pods.append(f"{name} ({ready}, {status})")
        if bad_pods:
            print(f"  {RED}✗ Unhealthy pods detected:{RESET} {', '.join(bad_pods)}")
            checks_passed = False
        else:
            print(f"  {GREEN}✓ All pods in '{ns}' are Running and Ready.{RESET}")

    # 2. Check Service Endpoints & Port 8080 on order-api
    print(f"{BOLD}[2/4] Checking Service Endpoints & TargetPorts in '{ns}'...{RESET}")
    ep_res = run_cmd(f"kubectl get ep order-api -n {ns} -o jsonpath='{{.subsets[*].ports[*].port}}' 2>/dev/null")
    netpol_res = run_cmd(f"kubectl get netpol deny-order-api-ingress -n {ns} --no-headers 2>/dev/null")
    if ep_res.returncode != 0 or "8080" not in (ep_res.stdout or ""):
        print(f"  {RED}✗ Service 'order-api' is missing healthy port 8080 endpoints (got: '{ep_res.stdout}').{RESET}")
        checks_passed = False
    elif netpol_res.returncode == 0 and "deny-order-api-ingress" in (netpol_res.stdout or ""):
        print(f"  {RED}✗ Rogue NetworkPolicy 'deny-order-api-ingress' is still blocking ingress.{RESET}")
        checks_passed = False
    else:
        print(f"  {GREEN}✓ Service 'order-api' endpoints and NetworkPolicies are healthy.{RESET}")

    # 3. Check Pending PVCs
    print(f"{BOLD}[3/4] Checking PersistentVolumeClaims in '{ns}'...{RESET}")
    pvc_res = run_cmd(f"kubectl get pvc -n {ns} --no-headers 2>/dev/null")
    if pvc_res.returncode == 0 and "Pending" in (pvc_res.stdout or ""):
        print(f"  {RED}✗ Pending PersistentVolumeClaim detected in '{ns}'.{RESET}")
        checks_passed = False
    else:
        print(f"  {GREEN}✓ No stuck Pending PVCs in '{ns}'.{RESET}")

    # 4. Check Lula OSCAL Compliance (compare baseline vs live cluster state)
    print(f"{BOLD}[4/4] Running Lula DoD IL5 OSCAL Validation...{RESET}")
    lula_res = run_cmd(
        "cp docs/compliance/assessment-results.yaml /tmp/lula-drill-assessment.yaml && "
        "lula validate -f docs/compliance/oscal-il5.yaml -o /tmp/lula-drill-assessment.yaml"
    )
    eval_res = run_cmd("lula evaluate -f /tmp/lula-drill-assessment.yaml")
    if lula_res.returncode != 0 or eval_res.returncode != 0:
        print(f"  {RED}✗ Lula OSCAL compliance validation failed (control drift detected).{RESET}")
        checks_passed = False
    else:
        print(f"  {GREEN}✓ All NIST SP 800-53 Rev 5 Lula controls are SATISFIED.{RESET}")

    print(f"\n{'=' * 84}")
    if checks_passed:
        print(f"{BOLD}{GREEN}✅ ALL CHECKS PASSED: Cluster and compliance controls are 100% healthy!{RESET}\n")
        if MYSTERY_STATE_FILE.exists():
            state = json.loads(MYSTERY_STATE_FILE.read_text())
            print(f"{BOLD}{CYAN}🏆 Mystery Solved! You remediated: {state['scenario_id']} ({state['title']}){RESET}\n")
            MYSTERY_STATE_FILE.unlink()
    else:
        print(f"{BOLD}{RED}❌ ISSUES REMAIN: Use `kubectl`, `zarf`, `uds`, or `lula` to investigate above failures.{RESET}\n")

    return checks_passed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Defense Unicorns & Kubernetes Interactive CLI Troubleshooting Drill Manager"
    )
    parser.add_argument("--list", action="store_true", help="List all available troubleshooting drill scenarios")
    parser.add_argument("--cheatsheet", action="store_true", help="Print CLI diagnostic reference card")
    parser.add_argument("--inject", type=str, metavar="ID", help="Scenario ID to inject")
    parser.add_argument("--heal", type=str, metavar="ID", help="Scenario ID to heal (or 'all')")
    parser.add_argument("--verify", type=str, metavar="ID", help="Verify live symptoms of a scenario")
    parser.add_argument("--tutor", type=str, metavar="ID", help="Launch interactive 4-phase CLI tutor for a scenario")
    parser.add_argument("--no-inject", action="store_true", help="Do not inject fault when starting --tutor")
    parser.add_argument("--mystery", action="store_true", help="Inject a random blind scenario for mystery troubleshooting")
    parser.add_argument("--check", action="store_true", help="Audit cluster & Lula compliance health")
    parser.add_argument("--reveal", action="store_true", help="Reveal the active mystery scenario during --check")
    parser.add_argument("--namespace", type=str, default=None, help="Override training workload namespace")

    args = parser.parse_args()
    offline_only = args.list or args.cheatsheet or len(sys.argv) == 1
    ns = args.namespace or detect_training_namespace(query_cluster=not offline_only)
    scenarios = build_scenarios(ns)

    if args.list or len(sys.argv) == 1:
        list_drills(scenarios)
    elif args.cheatsheet:
        print_cheatsheet(ns)
    elif args.inject:
        if not inject_drill(args.inject, scenarios):
            sys.exit(1)
    elif args.heal:
        if not heal_drill(args.heal, scenarios):
            sys.exit(1)
    elif args.verify:
        verify_drill(args.verify, scenarios, ns)
    elif args.tutor:
        run_tutor(args.tutor, scenarios, inject_first=not args.no_inject)
    elif args.mystery:
        inject_mystery(scenarios)
    elif args.check:
        if not check_cluster_health(scenarios, ns, reveal=args.reveal):
            sys.exit(1)


if __name__ == "__main__":
    main()
