[Setup]
AppName=HK
AppVersion=1.0.3
AppPublisher=HK
DefaultDirName={autopf}\HK
OutputDir=D:\Program Files\shop
OutputBaseFilename=hookstoresetup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=D:\Program Files\shop\hook_shop.ico
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

[InstallDelete]
Type: filesandordirs; Name: "{app}\blueprints"
Type: filesandordirs; Name: "{app}\database"
Type: filesandordirs; Name: "{app}\services"
Type: filesandordirs; Name: "{app}\templates"
Type: filesandordirs; Name: "{app}\static"
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\app.py"
Type: files; Name: "{app}\config.py"
Type: files; Name: "{app}\helpers.py"
Type: files; Name: "{app}\requirements.txt"
Type: files; Name: "{app}\app_error.log"

[Files]
Source: "D:\Program Files\shop\dist\HookShop\HookShop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\Program Files\shop\dist\HookShop\_internal\*"; DestDir: "{app}\_internal"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "D:\Program Files\shop\hk_codesign.cer"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\HK"; Filename: "{app}\HookShop.exe"; IconFilename: "{app}\_internal\hook_shop.ico"; Comment: "HK - نظام نقطة البيع"
Name: "{group}\HK"; Filename: "{app}\HookShop.exe"; IconFilename: "{app}\_internal\hook_shop.ico"
Name: "{group}\Uninstall HK"; Filename: "{uninstallexe}"

[Run]
Filename: "certutil.exe"; Parameters: "-f -user -addstore Root ""{app}\hk_codesign.cer"""; Flags: runhidden waituntilterminated
Filename: "certutil.exe"; Parameters: "-f -user -addstore TrustedPublisher ""{app}\hk_codesign.cer"""; Flags: runhidden waituntilterminated
Filename: "{app}\HookShop.exe"; Description: "تشغيل HK الآن"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\shop_backup"
Type: filesandordirs; Name: "{app}\qr_codes"
Type: files; Name: "{app}\shop.db"
Type: files; Name: "{app}\.secret_key"
Type: files; Name: "{app}\FIRST_LOGIN.txt"
Type: files; Name: "{app}\app_error.log"
Type: files; Name: "{autodesktop}\HK.lnk"
