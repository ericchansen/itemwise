<#
.SYNOPSIS
    Deploy script for Itemwise - builds Docker image and deploys to Azure.

.DESCRIPTION
    This script handles local Docker builds and Azure deployment to avoid
    GitHub Actions timeouts caused by HuggingFace model downloads.

.PARAMETER Command
    The deployment command to run:
    - build:  Build Docker image locally
    - push:   Push image to Azure Container Registry
    - up:     Deploy/update Azure resources and Container App
    - down:   Tear down Azure resources
    - all:    Full deploy (build + push + up)
    - status: Show deployment status

.EXAMPLE
    .\scripts\deploy.ps1 build
    .\scripts\deploy.ps1 all
    .\scripts\deploy.ps1 down
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "push", "up", "down", "all", "status", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

# Configuration
$ImageName = "itemwise"
$ImageTag = "latest"

function Write-Step {
    param([string]$Message)
    Write-Host "`n▸ $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Get-AzdEnv {
    # Get environment variables from azd
    $env = azd env get-values 2>$null | ConvertFrom-StringData
    return $env
}

function Test-Prerequisites {
    Write-Step "Checking prerequisites..."
    
    $missing = @()
    
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        $missing += "docker"
    }
    
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        $missing += "az (Azure CLI)"
    }
    
    if (-not (Get-Command azd -ErrorAction SilentlyContinue)) {
        $missing += "azd (Azure Developer CLI)"
    }
    
    if ($missing.Count -gt 0) {
        Write-Error "Missing required tools: $($missing -join ', ')"
        exit 1
    }
    
    Write-Success "All prerequisites found"
}

function Invoke-Build {
    Write-Step "Building Docker image..."
    
    docker build -t "${ImageName}:${ImageTag}" .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        exit 1
    }
    
    Write-Success "Built ${ImageName}:${ImageTag}"
}

function Invoke-Push {
    Write-Step "Pushing to Azure Container Registry..."
    
    # Get ACR name from azd environment
    $acrName = azd env get-value AZURE_CONTAINER_REGISTRY_NAME 2>$null
    if (-not $acrName) {
        Write-Error "AZURE_CONTAINER_REGISTRY_NAME not set. Run 'azd provision' first."
        exit 1
    }
    
    $acrEndpoint = azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT 2>$null
    if (-not $acrEndpoint) {
        Write-Error "AZURE_CONTAINER_REGISTRY_ENDPOINT not set. Run 'azd provision' first."
        exit 1
    }
    
    Write-Host "  ACR: $acrEndpoint"
    
    # Login to ACR
    Write-Step "Logging in to ACR..."
    az acr login --name $acrName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ACR login failed"
        exit 1
    }
    
    # Tag and push
    $remoteTag = "${acrEndpoint}/${ImageName}:${ImageTag}"
    
    Write-Step "Tagging image..."
    docker tag "${ImageName}:${ImageTag}" $remoteTag
    
    Write-Step "Pushing image..."
    docker push $remoteTag
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker push failed"
        exit 1
    }
    
    Write-Success "Pushed to $remoteTag"
}

function Invoke-Up {
    Write-Step "Deploying to Azure..."
    
    # Check if resources are provisioned
    $rg = azd env get-value AZURE_RESOURCE_GROUP 2>$null
    if (-not $rg) {
        Write-Step "Resources not provisioned. Running 'azd provision'..."
        azd provision
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Provisioning failed"
            exit 1
        }
    }
    
    # Deploy the app
    azd deploy
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Deployment failed"
        exit 1
    }
    
    # Show endpoint
    $endpoint = azd env get-value SERVICE_API_ENDPOINT 2>$null
    Write-Success "Deployed successfully!"
    Write-Host "`n  Endpoint: $endpoint" -ForegroundColor Yellow
}

function Invoke-Down {
    Write-Step "Tearing down Azure resources..."
    
    $envName = azd env get-value AZURE_ENV_NAME 2>$null
    if (-not $envName) {
        Write-Error "No Azure environment found. Nothing to tear down."
        exit 0
    }
    
    Write-Host "  This will delete all resources in environment: $envName" -ForegroundColor Yellow
    $confirm = Read-Host "  Are you sure? (y/N)"
    
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "  Cancelled."
        exit 0
    }
    
    azd down --force --purge
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tear down failed"
        exit 1
    }
    
    Write-Success "Resources deleted"
}

function Invoke-Status {
    Write-Step "Deployment Status"
    
    $envName = azd env get-value AZURE_ENV_NAME 2>$null
    $rg = azd env get-value AZURE_RESOURCE_GROUP 2>$null
    $endpoint = azd env get-value SERVICE_API_ENDPOINT 2>$null
    $acr = azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT 2>$null
    
    Write-Host ""
    Write-Host "  Environment:  $($envName ?? 'Not set')"
    Write-Host "  Resource Group: $($rg ?? 'Not provisioned')"
    Write-Host "  ACR:          $($acr ?? 'Not provisioned')"
    Write-Host "  Endpoint:     $($endpoint ?? 'Not deployed')"
    
    if ($endpoint) {
        Write-Host ""
        Write-Step "Testing endpoint..."
        try {
            $response = Invoke-WebRequest -Uri "$endpoint/api/items" -TimeoutSec 10 -UseBasicParsing
            Write-Success "API is responding (HTTP $($response.StatusCode))"
        } catch {
            Write-Error "API not responding: $_"
        }
    }
}

function Show-Help {
    Write-Host @"

Itemwise Deploy Script
======================

Usage: .\scripts\deploy.ps1 <command>

Commands:
  build   Build Docker image locally
  push    Push image to Azure Container Registry
  up      Deploy/update Azure resources and Container App
  down    Tear down all Azure resources
  all     Full deploy (build + push + up)
  status  Show deployment status
  help    Show this help message

Examples:
  .\scripts\deploy.ps1 build      # Build image only
  .\scripts\deploy.ps1 all        # Full deployment
  .\scripts\deploy.ps1 down       # Delete all resources

Prerequisites:
  - Docker Desktop
  - Azure CLI (az)
  - Azure Developer CLI (azd)
  - Azure subscription with appropriate permissions

"@
}

# Main
switch ($Command) {
    "build" {
        Test-Prerequisites
        Invoke-Build
    }
    "push" {
        Test-Prerequisites
        Invoke-Push
    }
    "up" {
        Test-Prerequisites
        Invoke-Up
    }
    "down" {
        Test-Prerequisites
        Invoke-Down
    }
    "all" {
        Test-Prerequisites
        Invoke-Build
        Invoke-Push
        Invoke-Up
    }
    "status" {
        Invoke-Status
    }
    "help" {
        Show-Help
    }
}
