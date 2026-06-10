# AKS Copilot - AI Chatbot for AKS Troubleshooting & Operations

AKS Copilot is a chatbot that connects to a live Azure Kubernetes Service (AKS)
cluster, diagnoses real-time failures (CrashLoopBackOff, pending pods, networking
issues, node pressure, etc.), and can create or modify Kubernetes objects (Pods,
Deployments, Services, Secrets, ConfigMaps) on request - all powered entirely by
**Azure AI** services: **Azure OpenAI (GPT-4o)** for tool-calling/streaming chat,
and **Azure AI Search** + **Azure AI Foundry** for retrieval-augmented (RAG)
troubleshooting guidance grounded in internal runbooks.

## Architecture

```
┌─────────────┐        SSE stream        ┌──────────────────────┐
│  React UI    │ ───────────────────────▶ │  FastAPI backend      │
│ (chat, tool  │ ◀─────────────────────── │  (Azure OpenAI tool   │
│  call view)  │                          │   calling + RAG)      │
└─────────────┘                          └──────────┬────────────┘
                                                      │
                  ┌───────────────────────────────────┼───────────────────────┐
                  ▼                                    ▼                       ▼
        ┌───────────────────┐              ┌────────────────────┐   ┌──────────────────┐
        │ Kubernetes API     │              │ Azure OpenAI        │   │ Azure AI Search    │
        │ (in-cluster SA +   │              │ GPT-4o + embeddings │   │ aks-runbooks-index │
        │  RBAC, read/write) │              └────────────────────┘   └──────────────────┘
        └───────────────────┘
                  ▲
                  │
        ┌───────────────────┐
        │ Azure AI Foundry    │  Hub + Project: connections to OpenAI & AI Search,
        │ (Hub + Project)     │  shared governance/tracking for the chatbot
        └───────────────────┘
```

## Repository layout

```
backend/                FastAPI app (Azure OpenAI tool-calling, K8s client, RAG, SSE)
  app/
    core/config.py       Settings (env vars)
    models/schemas.py     Pydantic request/response models
    services/
      kubernetes_service.py  K8s client wrapper (in-cluster or kubeconfig)
      openai_service.py      Azure OpenAI streaming + tool-calling orchestration
      search_service.py      Azure AI Search RAG queries
      streaming_service.py   SSE formatting helpers
    tools/
      k8s_diagnostic_tools.py  Read-only tools (get_pods, get_pod_logs, describe_pod, ...)
      k8s_mutation_tools.py    Mutating tools (create_pod/deployment/service/secret/configmap, scale, restart, delete)
    api/
      chat.py    POST /api/chat/stream (SSE)
      health.py  /healthz, /readyz
  tests/                 pytest unit tests
  Dockerfile

frontend/               React + Vite chat UI (dark theme, streaming, tool-call viewer)
  src/
    components/  ChatWindow, MessageBubble, ToolCallDisplay, KubernetesObjectPreview
    services/api.js  SSE client
  Dockerfile, nginx.conf

infra/
  bicep/
    main.bicep            Orchestrates everything below
    ai-hub.bicep           Azure AI Foundry Hub (+ OpenAI/Search connections)
    ai-project.bicep       Azure AI Foundry Project
    ai-search.bicep        Azure AI Search service
    container-apps.bicep   Optional Container Apps hosting path
    modules/
      openai.bicep          Azure OpenAI: GPT-4o + text-embedding-3-small deployments
      keyvault.bicep, storage.bicep, container-registry.bicep, log-analytics.bicep
      role-assignments.bicep  Least-privilege RBAC for OpenAI + AI Search
  runbooks/               Markdown troubleshooting runbooks indexed for RAG
  scripts/
    setup.sh              One-shot infra bootstrap + GitHub OIDC service principal
    index-k8s-docs.py     Embeds + uploads runbooks to Azure AI Search

k8s/                     In-cluster deployment manifests
  namespace.yaml, serviceaccount.yaml, rbac.yaml, configmap.yaml, secret.yaml
  deployment.yaml, service.yaml, hpa.yaml, ingress.yaml

.github/workflows/
  build-push.yml      Test, build, scan (Trivy), push images to GHCR
  infra-deploy.yml    Deploy Azure AI infra via Bicep (OIDC)
  index-runbooks.yml  (Re)build the AI Search RAG index
  app-deploy.yml      Deploy to AKS (kubectl apply + rollout + smoke test)
```

## How the chatbot works

1. **Streaming chat** - `POST /api/chat/stream` streams Server-Sent Events: `token`
   (assistant text), `tool_call` (started/completed/failed with arguments + result),
   and `done`.
2. **Tool calling** - GPT-4o is given two sets of OpenAI function-calling tools:
   - **Diagnostics** (read-only): `get_pods`, `get_pod_logs`, `describe_pod`,
     `get_events`, `get_deployments`, `get_services`, `get_nodes`, `check_pod_health`.
   - **Mutations**: `create_pod`, `create_deployment`, `create_service`,
     `create_secret`, `create_configmap`, `delete_resource`, `scale_deployment`,
     `restart_deployment`.
   The backend dispatches tool calls to the Kubernetes Python client
   (`app/services/kubernetes_service.py`), which loads in-cluster credentials and
   enforces a namespace allowlist (`KUBE_NAMESPACE_ALLOWLIST`) and a global
   mutation kill-switch (`ENABLE_MUTATIONS`).
3. **RAG grounding** - before calling GPT-4o, the backend queries Azure AI Search
   (hybrid vector + keyword) over `infra/runbooks/*.md` for relevant troubleshooting
   guidance and injects it as additional context, so remediation advice is grounded
   in the team's own runbooks.
4. **Azure AI Foundry** - the Hub + Project workspaces provide governed connections
   to the Azure OpenAI and AI Search resources (AAD auth, shared across future AI
   projects) and a place to track the chatbot as an AI Foundry project.

## Deploying

### 1. Provision Azure AI infrastructure

```bash
cd infra/scripts
./setup.sh aks-copilot-rg eastus akscopilot
```

This deploys (via `infra/bicep/main.bicep`):
- Azure OpenAI account with `gpt-4o` and `text-embedding-3-small` deployments
- Azure AI Search service
- Azure AI Foundry Hub + Project (with connections to OpenAI and AI Search)
- ACR, Key Vault, Storage Account, Log Analytics + App Insights
- (Optional) Container Apps environment + backend/frontend apps
- Role assignments granting the Hub/Project/Container App identities
  `Cognitive Services OpenAI User` and `Search Index Data Reader` /
  `Search Service Contributor`

It also creates a GitHub Actions OIDC service principal with federated
credentials and prints the secrets to add to the repo.

### 2. Index the AKS troubleshooting runbooks (RAG)

```bash
export AZURE_OPENAI_ENDPOINT=...  AZURE_OPENAI_API_KEY=...
export AZURE_SEARCH_ENDPOINT=...  AZURE_SEARCH_API_KEY=...
python infra/scripts/index-k8s-docs.py
```

Or just push changes to `infra/runbooks/` - the `index-runbooks.yml` workflow runs
this automatically.

### 3. Configure GitHub repo secrets

| Secret | Description |
| --- | --- |
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | OIDC federated credentials from `setup.sh` |
| `AZURE_RESOURCE_GROUP` | Resource group from `setup.sh` |
| `AKS_CLUSTER_NAME` | Target AKS cluster name |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | From the `openAi` module outputs |
| `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY` | From the `aiSearch` module outputs |

### 4. Deploy the chatbot to AKS

Push to `main` (or run manually):
- `build-push.yml` builds/tests/scans/pushes `aks-copilot-backend` and
  `aks-copilot-frontend` images to GHCR.
- `app-deploy.yml` applies `k8s/` manifests (namespace, RBAC, ServiceAccount,
  ConfigMap/Secret, Deployments, Services, HPA, Ingress), waits for rollout, and
  runs a `/healthz` smoke test.

The backend runs with a dedicated `aks-copilot-sa` ServiceAccount bound to a
ClusterRole (`k8s/rbac.yaml`) granting only the verbs needed by the diagnostic and
mutation tools, scoped to the namespaces in `KUBE_NAMESPACE_ALLOWLIST`.

## Local development

```bash
# Backend
cd backend
cp .env.example .env   # fill in Azure OpenAI / AI Search keys
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
cp .env.example .env
npm install
npm run dev
```

Or run both with Docker Compose:

```bash
docker compose up --build
```

## Safety controls

- `KUBE_NAMESPACE_ALLOWLIST` restricts which namespaces tools can touch.
- `ENABLE_MUTATIONS=false` disables all create/delete/scale/restart tools while
  keeping diagnostics available.
- All `create_*` tools support `dry_run: true` (server-side validation only).
- RBAC (`k8s/rbac.yaml`) limits the ServiceAccount to the resource kinds and verbs
  the tools actually use - no cluster-admin.

## Tests

```bash
cd backend && pytest -q
```
