[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [uri] $UploadUri,
    [Parameter(Mandatory = $true)]
    [string] $FilePath,
    [string] $FieldName = 'file',
    [string] $ExpectedRedirectPath = '/multipartException',
    [string] $CookieFile,
    [string[]] $ExtraForm = @(),
    [int] $TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
if (-not $UploadUri.IsAbsoluteUri -or $UploadUri.Scheme -ne 'https') {
    throw 'UploadUri must be an absolute HTTPS URL.'
}
if ($UploadUri.UserInfo) { throw 'Do not put credentials in the URL.' }
if ($FieldName -notmatch '^[A-Za-z0-9_.-]+$') {
    throw 'FieldName must be a simple multipart field name.'
}
if ($TimeoutSeconds -le 0) { throw 'TimeoutSeconds must be positive.' }
$taskFile = (Resolve-Path -LiteralPath $FilePath).Path
if (-not (Test-Path -LiteralPath $taskFile -PathType Leaf)) {
    throw 'FilePath must name an existing test file.'
}
if ($taskFile -match '[,;\"]') {
    throw 'Use a test file path without commas, semicolons or double quotes.'
}
$taskCurl = (Get-Command curl.exe -ErrorAction Stop).Source
$taskHeaders = [System.IO.Path]::GetTempFileName()
try {
    $taskArgs = @(
        '--silent', '--show-error', '--max-time', [string]$TimeoutSeconds,
        '--dump-header', $taskHeaders, '--output', 'NUL',
        '--write-out', '%{http_code}', '--header', 'Expect:',
        '--form', ($FieldName + '=@' + $taskFile)
    )
    if ($CookieFile) {
        $taskCookie = (Resolve-Path -LiteralPath $CookieFile).Path
        $taskArgs += @('--cookie', $taskCookie)
    }
    foreach ($taskForm in $ExtraForm) {
        $taskArgs += @('--form-string', $taskForm)
    }
    $taskArgs += $UploadUri.AbsoluteUri
    $taskStatus = (& $taskCurl @taskArgs | Out-String).Trim()
    $taskExit = $LASTEXITCODE
    if ($taskExit -ne 0) {
        throw "curl failed with exit code $taskExit; review early upload termination separately."
    }
    if ($taskStatus -ne '302') {
        throw "Expected HTTP 302 from the existing filter; received $taskStatus."
    }
    $taskRaw = [System.IO.File]::ReadAllText($taskHeaders)
    $taskLocations = [regex]::Matches($taskRaw, '(?im)^Location:\s*([^\r\n]+)')
    if ($taskLocations.Count -ne 1) {
        throw 'Expected exactly one Location header without following redirects.'
    }
    $taskLocation = $taskLocations[0].Groups[1].Value.Trim()
    $taskRedirect = $null
    if (-not [uri]::TryCreate($taskLocation, [UriKind]::Absolute, [ref]$taskRedirect)) {
        throw 'Location must be an absolute HTTPS URL for this acceptance test.'
    }
    if ($taskRedirect.Scheme -ne 'https' -or $taskRedirect.UserInfo) {
        throw 'Location has an unexpected scheme or embedded credentials.'
    }
    if ($taskRedirect.DnsSafeHost -ne $UploadUri.DnsSafeHost -or
        $taskRedirect.Port -ne $UploadUri.Port) {
        throw 'Location must retain the expected public host and public port.'
    }
    if ($taskRedirect.AbsolutePath -cne $ExpectedRedirectPath) {
        throw 'Location does not point to the expected exception page.'
    }
    [pscustomobject]@{
        Result = 'PASS'
        Status = 302
        Scheme = $taskRedirect.Scheme
        Host = $taskRedirect.DnsSafeHost
        Port = $taskRedirect.Port
        Path = $taskRedirect.AbsolutePath
        FollowedRedirects = $false
    }
}
finally {
    if (Test-Path -LiteralPath $taskHeaders) {
        Remove-Item -LiteralPath $taskHeaders -Force
    }
}
