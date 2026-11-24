; DocLens Windows installer (requires the onedir PyInstaller build).
#define AppVersion "0.6.0"

[Setup]
AppId={{7425DB23-1334-4479-A52B-687DE71D1057}
AppName=DocLens
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\DocLens
DefaultGroupName=DocLens
OutputDir=..\dist
OutputBaseFilename=DocLens-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\DocLens.exe
DisableProgramGroupPage=yes
SetupLogging=yes

[Files]
Source: "..\dist\DocLens\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DocLens"; Filename: "{app}\DocLens.exe"
Name: "{autodesktop}\DocLens"; Filename: "{app}\DocLens.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "其他选项："; Flags: unchecked

[Run]
Filename: "{app}\DocLens.exe"; Description: "运行 DocLens"; Flags: nowait postinstall skipifsilent
