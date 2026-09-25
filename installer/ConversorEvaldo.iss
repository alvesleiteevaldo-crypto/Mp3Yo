[Setup]
AppId={{7F0E2AA4-9D6B-4A7D-AF26-2E4A1F0E6B90}
AppName=Converte MP3 Sem Limite Evaldo
AppVersion=1.1.0
AppPublisher=Evaldo
DefaultDirName={autopf}\Converte MP3 Sem Limite Evaldo
DefaultGroupName=Converte MP3 Sem Limite Evaldo
OutputDir=.
OutputBaseFilename=Converte-MP3-Sem-Limite-Evaldo-Setup-Windows10-11-x64
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
Name: "{autoprograms}\Converte MP3 Sem Limite Evaldo"; Filename: "{app}\RedesSociaisDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\Converte MP3 Sem Limite Evaldo"; Filename: "{app}\RedesSociaisDownloader.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\RedesSociaisDownloader.exe"; Description: "Abrir Converte MP3 Sem Limite Evaldo"; Flags: nowait postinstall skipifsilent
