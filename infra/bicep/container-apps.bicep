@description('Azure Container Apps environment + the AKS Copilot backend/frontend apps. Optional hosting path for environments that prefer not to run the bot in-cluster (the primary path is k8s/deployment.yaml inside the target AKS cluster).')
param location string
param namePrefix string
param tags object = {}
param logAnalyticsWorkspaceId string
param acrLoginServer string
param backendImage string = '${acrLoginServer}/aks-copilot-backend:latest'
param frontendImage string = '${acrLoginServer}/aks-copilot-frontend:latest'

@description('Base64 kubeconfig for the target AKS cluster, stored as a Container Apps secret (only required for the Container Apps hosting path).')
@secure()
param targetKubeconfig string = ''

param azureOpenAiEndpoint string
param azureOpenAiDeployment string = 'gpt-4o'
param azureSearchEndpoint string
param azureSearchIndex string = 'aks-runbooks-index'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-cae'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-backend'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: empty(targetKubeconfig) ? [] : [
        { name: 'kubeconfig', value: targetKubeconfig }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat([
            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAiDeployment }
            { name: 'AZURE_SEARCH_ENDPOINT', value: azureSearchEndpoint }
            { name: 'AZURE_SEARCH_INDEX', value: azureSearchIndex }
            { name: 'KUBE_NAMESPACE_ALLOWLIST', value: 'default,app,monitoring' }
            { name: 'ENABLE_MUTATIONS', value: 'true' }
          ], empty(targetKubeconfig) ? [] : [
            { name: 'KUBECONFIG', value: '/secrets/kubeconfig' }
          ])
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-frontend'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}

output backendPrincipalId string = backendApp.identity.principalId
output backendFqdn string = backendApp.properties.configuration.ingress.fqdn
output frontendFqdn string = frontendApp.properties.configuration.ingress.fqdn
