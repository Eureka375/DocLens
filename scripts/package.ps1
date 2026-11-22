param(
    [string]$OutputDirectory = "dist"
)

$project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $project ".venv/Scripts/python.exe"
$previousPath = $env:PATH
$previousConfigDir = $env:PYINSTALLER_CONFIG_DIR
Push-Location -LiteralPath $project
try {
    # Restrict DLL discovery to Windows and the Python environment selected above.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $project "build/pyinstaller-cache"
    $base = & $python -I -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the project Python environment." }
    $buildArguments = @(
        "-I", "-m", "PyInstaller", "--clean", "--onedir", "--windowed",
        "--name", "DocLens", "--distpath", $OutputDirectory,
        "--copy-metadata", "pypdfium2", "--copy-metadata", "pillow",
        "--workpath", "build/pyinstaller", "--specpath", "build",
        "--add-data", "$(Join-Path $project 'src/doclens/ui');doclens/ui",
        "--add-data", "$(Join-Path $project 'src/doclens/word_preview.ps1');doclens"
    )
    # Conda keeps these Python extension dependencies outside the base directory.
    $condaDlls = @(
        "sqlite3.dll", "libssl-3-x64.dll", "libcrypto-3-x64.dll", "libexpat.dll",
        "ffi.dll", "libmpdec-4.dll", "liblzma.dll", "libbz2.dll", "zlib.dll", "libzstd.dll"
    )
    foreach ($name in $condaDlls) {
        $dependency = Join-Path $base "Library/bin/$name"
        if (Test-Path -LiteralPath $dependency) {
            $buildArguments += @("--add-binary", "$dependency;.")
        }
    }
    # PyInstaller resolves launcher and resource paths independently of the .spec folder.
    $buildArguments += (Join-Path $PSScriptRoot "launcher.py")
    & $python @buildArguments
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller could not build the Windows bundle." }
}
finally {
    $env:PATH = $previousPath
    $env:PYINSTALLER_CONFIG_DIR = $previousConfigDir
    Pop-Location
}
