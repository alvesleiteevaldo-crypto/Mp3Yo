[Setup]
AppId={{7F0E2AA4-9D6B-4A7D-AF26-2E4A1F0E6B90}
AppName=FluxMídia
AppVersion=1.2.0
AppPublisher=Evaldo
DefaultDirName={autopf}\FluxMidia
DefaultGroupName=FluxMidia
OutputDir=.
OutputBaseFilename=FluxMidia-Setup-Windows10-11-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\app_icon.ico
PrivilegesRequired=admin
DisableProgramGroupPage=yes

[Files]
Source: "package\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\FluxMídia"; Filename: "{app}\RedesSociaisDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\FluxMídia"; Filename: "{app}\RedesSociaisDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\RedesSociaisDownloader.exe"; Description: "Abrir FluxMídia"; Flags: nowait postinstall skipifsilent
