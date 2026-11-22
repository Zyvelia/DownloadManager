#ifndef AppVersion
  #define AppVersion "2.2.0"
#endif
#ifndef BuildDir
  #define BuildDir "..\dist"
#endif

[Setup]
AppId={{DDA3A390-7058-412A-AEC0-E9044DE2403F}
AppName=Z's Download Manager
AppVersion={#AppVersion}
AppPublisher=Zyvelia
AppPublisherURL=https://github.com/Zyvelia/DownloadManager
AppUpdatesURL=https://github.com/Zyvelia/DownloadManager/releases/latest
DefaultDirName={localappdata}\Programs\Zs Download Manager
DefaultGroupName=Z's Download Manager
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\Zs-Download-Manager.exe
OutputDir={#BuildDir}
OutputBaseFilename=Zs-Download-Manager-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#BuildDir}\Zs-Download-Manager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Z's Download Manager"; Filename: "{app}\Zs-Download-Manager.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Z's Download Manager"; Filename: "{app}\Zs-Download-Manager.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Zs-Download-Manager.exe"; Description: "Launch Z's Download Manager"; Flags: nowait postinstall skipifsilent
