param([string]$Source, [string]$Destination, [string]$PidFile, [string]$CancelFile)
$ErrorActionPreference = 'Stop'
$doclensWord = $null
$doclensDocument = $null
$probeDocument = $null
$ownsWord = $false
try {
    if (Test-Path -LiteralPath $CancelFile) { throw 'Cancelled.' }
    $existing = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $doclensWord = New-Object -ComObject Word.Application
    $probeDocument = $doclensWord.Documents.Add()
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class DocLensWordWindow { [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p); }'
    [uint32]$wordProcessId = 0
    [void][DocLensWordWindow]::GetWindowThreadProcessId([IntPtr]$probeDocument.ActiveWindow.Hwnd, [ref]$wordProcessId)
    if ($wordProcessId -eq 0 -or $existing -contains $wordProcessId) {
        throw 'Could not obtain an isolated Word instance.'
    }
    $ownsWord = $true
    [IO.File]::WriteAllText($PidFile, [string]$wordProcessId)
    if (Test-Path -LiteralPath $CancelFile) { throw 'Cancelled.' }
    $dontSave = 0
    $probeDocument.Close([ref]$dontSave)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($probeDocument)
    $probeDocument = $null
    $doclensWord.Visible = $false
    $doclensWord.DisplayAlerts = 0
    $doclensWord.AutomationSecurity = 3
    $oldLinks = $doclensWord.Options.UpdateLinksAtOpen
    $doclensWord.Options.UpdateLinksAtOpen = $false
    $doclensDocument = $doclensWord.Documents.Open($Source, $false, $true, $false)
    $doclensDocument.ExportAsFixedFormat($Destination, 17)
}
finally {
    $dontSave = 0
    try {
        if ($null -ne $probeDocument) { $probeDocument.Close([ref]$dontSave) }
        if ($null -ne $doclensDocument) { $doclensDocument.Close([ref]$dontSave) }
    }
    finally {
        if ($ownsWord) {
            if ($null -ne $oldLinks) { $doclensWord.Options.UpdateLinksAtOpen = $oldLinks }
            $doclensWord.Quit([ref]$dontSave)
        }
    }
    if ($null -ne $probeDocument) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($probeDocument) }
    if ($null -ne $doclensDocument) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doclensDocument) }
    if ($null -ne $doclensWord) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doclensWord) }
}
