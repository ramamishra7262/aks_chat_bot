#!/usr/bin/env bash
# Bootstraps the Azure AI infrastructure for AKS Copilot:
#   - Resource group
#   - AI Foundry Hub + Project, Azure OpenAI (GPT-4o + embeddings), Azure AI Search
#   - ACR, Key Vault, Storage, Log Analytics, Container Apps (optional)
#   - GitHub Actions OIDC service principal (federated credentials)
#
# Usage:
#   ./setup.sh <resource-group> <location> <name-prefix>
set -euo pipefail

RESOURCE_GROUP="${1:-aks-copilot-rg}"
LOCATION="${2:-eastus}"
NAME_PREFIX="${3:-akscopilot}"
GITHUB_ORG="ramamishra7262"
GITHUB_REPO="aks_chat_bot"

echo ">> Creating resource group ${RESOURCE_GROUP} in ${LOCATION}"
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}"

echo ">> Deploying AI infrastructure (Bicep)"
az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file "$(dirname "$0")/../bicep/main.bicep" \
  --parameters namePrefix="${NAME_PREFIX}" location="${LOCATION}"

echo ">> Creating GitHub Actions OIDC service principal"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
APP_ID=$(az ad app create --display-name "${NAME_PREFIX}-github-oidc" --query appId -o tsv)
az ad sp create --id "${APP_ID}" >/dev/null

az role assignment create \
  --assignee "${APP_ID}" \
  --role "Contributor" \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"

for ENTITY in \
  "github-main:repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main" \
  "github-pr:repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request"
do
  NAME="${ENTITY%%:*}"
  SUBJECT="${ENTITY#*:}"
  az ad app federated-credential create --id "${APP_ID}" --parameters "{
    \"name\": \"${NAME}\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"${SUBJECT}\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"
done

echo ""
echo "=== Done ==="
echo "Add these as GitHub repo secrets (Settings > Secrets and variables > Actions):"
echo "  AZURE_CLIENT_ID:       ${APP_ID}"
echo "  AZURE_TENANT_ID:       $(az account show --query tenantId -o tsv)"
echo "  AZURE_SUBSCRIPTION_ID: ${SUBSCRIPTION_ID}"
echo "  AZURE_RESOURCE_GROUP:  ${RESOURCE_GROUP}"
