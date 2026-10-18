param(
    [Parameter(Mandatory = $true)]
    [string]$DataRoot
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$configDb = Join-Path (Resolve-Path -LiteralPath $DataRoot).Path 'system\nexusdb_config.sqlite'
if (-not (Test-Path -LiteralPath $configDb -PathType Leaf)) {
    throw "Configuração não encontrada: $configDb. Informe a pasta NEXUSDB_DATA_ROOT da instância correta."
}
$helper = Join-Path $repoRoot 'target\debug\examples\reset_admin_password.exe'
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) {
    throw "Compile primeiro: cargo build --manifest-path `"$repoRoot\Cargo.toml`" --example reset_admin_password"
}
Write-Host "Recuperando admin em: $configDb"
$password = Read-Host 'Nova senha (mínimo 12 caracteres)' -AsSecureString
$confirmation = Read-Host 'Repita a nova senha' -AsSecureString
$passwordPtr = [IntPtr]::Zero
$confirmationPtr = [IntPtr]::Zero
try {
    $passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
    $confirmationPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirmation)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
    $again = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($confirmationPtr)
    if ($plain -cne $again) { throw 'As senhas não coincidem; nada foi alterado.' }
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $helper
    $start.Arguments = '--config-db "' + $configDb + '"'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $start.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    [void]$process.Start()
    $passwordBytes = [System.Text.Encoding]::UTF8.GetBytes($plain + "`n")
    $process.StandardInput.BaseStream.Write($passwordBytes, 0, $passwordBytes.Length)
    $process.StandardInput.BaseStream.Flush()
    $process.StandardInput.Close()
    $output = $process.StandardOutput.ReadToEnd()
    $failure = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw $failure.Trim() }
    Write-Host $output.Trim()
} finally {
    if ($passwordPtr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr) }
    if ($confirmationPtr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($confirmationPtr) }
    $plain = $null
    $again = $null
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    if ($password) { $password.Dispose() }
    if ($confirmation) { $confirmation.Dispose() }
    if ($process) { $process.Dispose() }
}