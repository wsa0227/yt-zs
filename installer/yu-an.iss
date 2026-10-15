; Inno Setup configuration for the Yu'an desktop application.
; Compile only after the PyInstaller output has been verified on Windows.

#define MyAppName "宇安"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "宇安"
#define MyAppExeName "LumbarRehabAssistant.exe"

[Setup]
AppId={{6D8F0E6D-8F19-4B50-9C8E-6C9A3F3A7A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\YuAn
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=YuAn-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
RestartApplications=no
CloseApplicationsFilter={#MyAppExeName}
UninstallDisplayName={#MyAppName}
; No signing certificate is configured. SmartScreen warning risk remains.

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动{#MyAppName}"; Flags: nowait postinstall skipifsilent

[Registry]
; Uninstall cleanup only removes this app's own current-user startup value.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "LumbarRehabAssistant"; Flags: uninsdeletevalue

; User health data is under %LOCALAPPDATA% and is intentionally preserved.
; Do not add the application data directory here.
