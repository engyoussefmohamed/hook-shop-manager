[Setup]
AppName=HK
AppVersion=1.0.3
AppPublisher=HK
DefaultDirName={autopf}\HK
DefaultGroupName=HK
OutputDir=D:\Program Files\HK
OutputBaseFilename=ShopSetup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=D:\Program Files\HK\hook_HK.ico
UninstallDisplayIcon={app}\HookShop.exe
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=no
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Files]
Source: "D:\Program Files\HK\dist\HookShop\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\HK"; Filename: "{app}\HookShop.exe"; WorkingDir: "{app}"; IconFilename: "{app}\HookShop.exe"; Comment: "HK - نظام نقطة البيع"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\HK.db"
Type: files; Name: "{app}\.secret_key"
Type: files; Name: "{autodesktop}\HK.lnk"
