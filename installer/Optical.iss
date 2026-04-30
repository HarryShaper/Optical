[Setup]
AppName=Optical
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\Optical
DefaultGroupName=Optical
OutputDir=installer_output
OutputBaseFilename=Optical_Setup
SetupIconFile=..\assets\Icons\logo.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "..\dist\Optical\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Optical"; Filename: "{app}\Optical.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Optical"; Filename: "{app}\Optical.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{usersendto}\Optical"; Filename: "{app}\Optical.exe"; WorkingDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\Optical.exe"; Description: "Launch Optical"; Flags: nowait postinstall skipifsilent