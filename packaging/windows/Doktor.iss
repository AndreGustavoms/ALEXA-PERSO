#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppArch
  #define AppArch "x64"
#endif
#ifndef SourceRoot
  #define SourceRoot "..\.."
#endif
#ifndef OutputRoot
  #define OutputRoot "..\..\build\installers"
#endif

[Setup]
AppId={{A9176905-F9B5-4A55-859F-D250EBE8D5C0}
AppName=Doktor Assistant
AppVersion={#AppVersion}
AppPublisher=Doktor
AppPublisherURL=https://github.com/AndreGustavoms/ALEXA-PERSO
DefaultDirName={autopf}\Doktor Assistant
DefaultGroupName=Doktor Assistant
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputRoot}
OutputBaseFilename=Doktor-{#AppVersion}-win-{#AppArch}
SetupIconFile={#SourceRoot}\assets\doktor-assistant.ico
WizardImageFile={#SourceRoot}\assets\doktor-installer-wizard.png
WizardSmallImageFile={#SourceRoot}\assets\doktor-installer-small.png
UninstallDisplayIcon={app}\Doktor.exe
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
CloseApplications=yes
RestartApplications=yes
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Doktor
VersionInfoDescription=Doktor Assistant - assistente de voz local
VersionInfoProductName=Doktor Assistant
VersionInfoProductVersion={#AppVersion}

[Tasks]
Name: "autostart"; Description: "Iniciar Doktor junto com o Windows"; Flags: unchecked
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\build\pyinstaller\Doktor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Doktor Assistant"; Filename: "{app}\Doktor.exe"; Parameters: "--open"
Name: "{autodesktop}\Doktor Assistant"; Filename: "{app}\Doktor.exe"; Parameters: "--open"; Tasks: desktopicon
Name: "{userstartup}\Doktor Assistant"; Filename: "{app}\Doktor.exe"; Tasks: autostart

[Run]
Filename: "{app}\Doktor.exe"; Parameters: "--open"; Description: "Abrir Doktor Assistant"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Doktor.exe"; Parameters: "--stop"; Flags: runhidden skipifdoesntexist; RunOnceId: "StopDoktor"
