@description('Azure AI Foundry Project workspace, scoped under the AI Hub. The chatbot is registered/tracked here.')
param location string
param namePrefix string
param tags object = {}
param aiHubId string

resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: '${namePrefix}-aiproject'
  location: location
  tags: tags
  kind: 'Project'
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'AKS Copilot'
    description: 'AI Foundry project for the AKS Copilot AKS troubleshooting chatbot.'
    hubResourceId: aiHubId
  }
}

output aiProjectId string = aiProject.id
output aiProjectName string = aiProject.name
output aiProjectPrincipalId string = aiProject.identity.principalId
