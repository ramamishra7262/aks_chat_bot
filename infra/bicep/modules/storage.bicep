@description('Storage account backing the Azure AI Foundry hub (required for hub workspaces).')
param location string
param namePrefix string
param tags object = {}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: replace('${namePrefix}aihubsa', '-', '')
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

output storageAccountId string = storage.id
