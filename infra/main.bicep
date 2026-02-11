targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, staging, prod)')
param environmentName string

@description('Primary location for all resources')
param location string

@description('Azure OpenAI chat deployment name')
param azureOpenAiDeployment string = 'gpt-4o-mini'

@description('Azure OpenAI embedding deployment name')
param azureOpenAiEmbeddingDeployment string = 'text-embedding-3-small'

@description('PostgreSQL administrator password')
@secure()
param postgresPassword string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
}

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// Main infrastructure module
module resources './resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    azureOpenAiDeployment: azureOpenAiDeployment
    azureOpenAiEmbeddingDeployment: azureOpenAiEmbeddingDeployment
    postgresPassword: postgresPassword
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryEndpoint
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.containerRegistryName
output SERVICE_API_ENDPOINT string = resources.outputs.apiEndpoint
output POSTGRES_HOST string = resources.outputs.postgresHost
output POSTGRES_DATABASE string = resources.outputs.postgresDatabase
output AZURE_OPENAI_ENDPOINT string = resources.outputs.azureOpenAiEndpoint
