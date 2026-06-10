@description('Azure OpenAI account with GPT-4o (chat + tool calling) and text-embedding-3-small (RAG) deployments.')
param location string
param namePrefix string
param tags object = {}
param gpt4oCapacity int = 30
param embeddingCapacity int = 30

resource openai 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: '${namePrefix}-aoai'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${namePrefix}-aoai'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openai
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: gpt4oCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openai
  name: 'text-embedding-3-small'
  sku: {
    name: 'Standard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  dependsOn: [
    gpt4oDeployment
  ]
}

output openAiId string = openai.id
output openAiName string = openai.name
output openAiEndpoint string = openai.properties.endpoint
output openAiPrincipalId string = openai.identity.principalId
