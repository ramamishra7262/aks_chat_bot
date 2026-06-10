@description('Azure Container Registry for backend/frontend images.')
param location string
param namePrefix string
param tags object = {}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: replace('${namePrefix}acr', '-', '')
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

output acrId string = acr.id
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
