[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Tag,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string]$NotesFile,

    [Parameter(Mandatory = $true)]
    [string[]]$Asset,

    [string]$StatusFile
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (git rev-parse --show-toplevel).Trim()
$repoSlug = (git config --get remote.origin.url).Trim() -replace '^https://github.com/', '' -replace '^git@github.com:', '' -replace '\.git$', ''
$branch = (git branch --show-current).Trim()
$commit = (git rev-parse HEAD).Trim()
$gh = (Get-Command gh -ErrorAction Stop).Source

if ([string]::IsNullOrWhiteSpace($repoSlug) -or $repoSlug -notmatch '^[^/]+/[^/]+$') {
    throw "Could not resolve a GitHub owner/repository from origin."
}
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "A named branch is required for a review release."
}
if (-not (Test-Path -LiteralPath $NotesFile -PathType Leaf)) {
    throw "Release notes file does not exist: $NotesFile"
}

if ($StatusFile) {
    if (-not (Test-Path -LiteralPath $StatusFile -PathType Leaf)) {
        throw "Status file does not exist: $StatusFile"
    }
    $status = Get-Content -Raw -LiteralPath $StatusFile | ConvertFrom-Json
    if ($status.unityInputAllowed -ne $false) {
        throw "Refusing to publish a review release with unityInputAllowed=true."
    }
    if ($status.productionPromotionAllowed -ne $false) {
        throw "Refusing to publish a review release with productionPromotionAllowed=true."
    }
}

$resolvedAssets = @()
foreach ($path in $Asset) {
    $resolved = (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "Release asset is not a file: $resolved"
    }
    $item = Get-Item -LiteralPath $resolved
    $resolvedAssets += [ordered]@{
        name = $item.Name
        path = $resolved
        bytes = $item.Length
        sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$manifest = [ordered]@{
    schemaVersion = "re-camp-review-release-manifest-v001"
    repository = $repoSlug
    tag = $Tag
    title = $Title
    targetBranch = $branch
    targetCommit = $commit
    prerelease = $true
    assets = $resolvedAssets
}
$manifestPath = Join-Path ([IO.Path]::GetTempPath()) ("re-camp-review-release-{0}.manifest.json" -f $Tag)
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$releaseArgs = @(
    "release", "create", $Tag,
    "--repo", $repoSlug,
    "--target", $branch,
    "--title", $Title,
    "--notes-file", (Resolve-Path -LiteralPath $NotesFile).Path,
    "--prerelease"
)
$releaseArgs += ($resolvedAssets | ForEach-Object { $_.path })
$releaseArgs += $manifestPath

& $gh @releaseArgs
if ($LASTEXITCODE -ne 0) {
    throw "GitHub Release creation failed with exit code $LASTEXITCODE."
}

Write-Output ($manifest | ConvertTo-Json -Depth 6)
