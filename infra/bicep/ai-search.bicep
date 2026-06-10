@description('Azure AI Search service hosting the AKS/K8s runbook vector index used for RAG.')
param location string
param namePrefix string
param tags object = {}
param skuName string = 'basic'

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: '${namePrefix}-search'
  location: location
  tags: tags
  sku: { name: skuName }
  identity: { type: 'SystemAssigned' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    semanticSearch: 'free'
  }
}

output searchId string = search.id
output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output searchPrincipalId string = search.identity.principalId
