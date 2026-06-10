@description('AKS Copilot - Azure AI infrastructure: AI Foundry (Hub + Project), Azure OpenAI (GPT-4o + embeddings), Azure AI Search, ACR, Container Apps hosting, Key Vault, Storage, and Log Analytics/App Insights.')
param location string = resourceGroup().location

@minLength(3)
@maxLength(12)
@description('Short, lowercase, alphanumeric prefix used to derive resource names (e.g. akscopilot).')
param namePrefix string = 'akscopilot'

param tags object = {
  project: 'aks-chat-bot'
  managedBy: 'bicep'
}

@description('Deploy the Container Apps hosting path in addition to AI infra. The chatbot can alternatively run in-cluster via k8s/deployment.yaml.')
param deployContainerApps bool = true

@secure()
@description('Base64 kubeconfig for the target AKS cluster (only used if deployContainerApps=true and you want the bot to manage a remote cluster).')
param targetKubeconfig string = ''

// ---------------------------------------------------------------------
// Foundational resources
// ---------------------------------------------------------------------
module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module acr 'modules/container-registry.bicep' = {
  name: 'acr'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

// ---------------------------------------------------------------------
// Azure AI resources
// ---------------------------------------------------------------------
module openAi 'modules/openai.bicep' = {
  name: 'openAi'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module aiSearch 'ai-search.bicep' = {
  name: 'aiSearch'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module aiHub 'ai-hub.bicep' = {
  name: 'aiHub'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
    storageAccountId: storage.outputs.storageAccountId
    keyVaultId: keyVault.outputs.keyVaultId
    appInsightsId: logAnalytics.outputs.logAnalyticsId
    openAiEndpoint: openAi.outputs.openAiEndpoint
    openAiAccountId: openAi.outputs.openAiId
    searchEndpoint: aiSearch.outputs.searchEndpoint
    searchServiceId: aiSearch.outputs.searchId
  }
}

module aiProject 'ai-project.bicep' = {
  name: 'aiProject'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
    aiHubId: aiHub.outputs.aiHubId
  }
}

// ---------------------------------------------------------------------
// Hosting (optional Container Apps path)
// ---------------------------------------------------------------------
module containerApps 'container-apps.bicep' = if (deployContainerApps) {
  name: 'containerApps'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.logAnalyticsId
    acrLoginServer: acr.outputs.acrLoginServer
    azureOpenAiEndpoint: openAi.outputs.openAiEndpoint
    azureSearchEndpoint: aiSearch.outputs.searchEndpoint
    targetKubeconfig: targetKubeconfig
  }
}

// ---------------------------------------------------------------------
// Role assignments: grant Hub/Project + Container App identities access
// to Azure OpenAI and Azure AI Search using least-privilege built-in roles.
// ---------------------------------------------------------------------
module roleAssignments 'modules/role-assignments.bicep' = {
  name: 'roleAssignments'
  params: {
    openAiAccountName: openAi.outputs.openAiName
    searchServiceName: aiSearch.outputs.searchName
    principalIds: deployContainerApps ? [
      aiHub.outputs.aiHubPrincipalId
      aiProject.outputs.aiProjectPrincipalId
      containerApps.outputs.backendPrincipalId
    ] : [
      aiHub.outputs.aiHubPrincipalId
      aiProject.outputs.aiProjectPrincipalId
    ]
  }
}

// ---------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------
output resourceGroupLocation string = location
output azureOpenAiEndpoint string = openAi.outputs.openAiEndpoint
output azureOpenAiName string = openAi.outputs.openAiName
output azureSearchEndpoint string = aiSearch.outputs.searchEndpoint
output azureSearchName string = aiSearch.outputs.searchName
output aiHubName string = aiHub.outputs.aiHubName
output aiProjectName string = aiProject.outputs.aiProjectName
output acrLoginServer string = acr.outputs.acrLoginServer
output keyVaultName string = keyVault.outputs.keyVaultName
output appInsightsConnectionString string = logAnalytics.outputs.appInsightsConnectionString
output containerAppBackendFqdn string = deployContainerApps ? containerApps.outputs.backendFqdn : ''
output containerAppFrontendFqdn string = deployContainerApps ? containerApps.outputs.frontendFqdn : ''
