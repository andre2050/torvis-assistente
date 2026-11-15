#define MyAppName "T.O.R.V.I.S 2026"
#define MyAppVersion "6.0.0"
#define MyAppPublisher "Andre Luiz Lima Menezes"
#define MyAppExeName "TORVIS.exe"

[Setup]
AppId={{9F5B589A-4CF5-4D61-AF9D-3DAA42C6C07E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\TORVIS
DefaultGroupName=TORVIS
PrivilegesRequired=lowest
OutputDir=..\dist-installer
OutputBaseFilename=TORVIS-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\TORVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TORVIS"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\TORVIS"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "startup"; Description: "Iniciar TORVIS com o Windows"; GroupDescription: "Inicialização:"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "T.O.R.V.I.S 2026"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir TORVIS"; Flags: nowait postinstall skipifsilent
