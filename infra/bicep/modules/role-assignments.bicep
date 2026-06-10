@description('Grants the AKS Copilot identities the minimum Azure RBAC roles needed to call Azure OpenAI and Azure AI Search.')
param openAiAccountName string
param searchServiceName string
param principalIds array
param principalType string = 'ServicePrincipal'

// Built-in role definition IDs
var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'      // Search Index Data Reader
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'   // Search Service Contributor

resource openAi 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' existing = {
  name: openAiAccountName
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource openAiRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in principalIds: {
  name: guid(openAi.id, principalId, cognitiveServicesOpenAiUserRoleId)
  scope: openAi
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: principalId
    principalType: principalType
  }
}]

resource searchReaderAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in principalIds: {
  name: guid(search.id, principalId, searchIndexDataReaderRoleId)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReaderRoleId)
    principalId: principalId
    principalType: principalType
  }
}]

resource searchContributorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in principalIds: {
  name: guid(search.id, principalId, searchServiceContributorRoleId)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalId: principalId
    principalType: principalType
  }
}]
