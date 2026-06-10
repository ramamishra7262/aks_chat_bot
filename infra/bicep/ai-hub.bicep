@description('Azure AI Foundry Hub workspace - the shared management plane for AI Projects, connections to Azure OpenAI and AI Search.')
param location string
param namePrefix string
param tags object = {}
param storageAccountId string
param keyVaultId string
param appInsightsId string
param openAiEndpoint string
param openAiAccountId string
param searchEndpoint string
param searchServiceId string

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: '${namePrefix}-aihub'
  location: location
  tags: tags
  kind: 'Hub'
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'AKS Copilot AI Hub'
    description: 'AI Foundry hub for the AKS Copilot chatbot - hosts the OpenAI and AI Search connections used for cluster troubleshooting and RAG.'
    storageAccount: storageAccountId
    keyVault: keyVaultId
    applicationInsights: appInsightsId
  }
}

// Connection: Azure OpenAI (used for GPT-4o tool calling + embeddings)
resource openAiConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name: 'aoai-connection'
  properties: {
    category: 'AzureOpenAI'
    target: openAiEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: openAiAccountId
    }
  }
}

// Connection: Azure AI Search (used for runbook RAG index)
resource searchConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name: 'aisearch-connection'
  properties: {
    category: 'CognitiveSearch'
    target: searchEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchServiceId
    }
  }
}

output aiHubId string = aiHub.id
output aiHubName string = aiHub.name
output aiHubPrincipalId string = aiHub.identity.principalId
