; Script de Inno Setup. Lo usa el workflow de GitHub Actions (necesita dist\GestorSesiones.exe ya construido).
#define AppName "Gestor de Sesiones"
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{62B1CDB0-648C-4EB0-95A6-E97A83AC267A}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\GestorSesiones
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist_installer
OutputBaseFilename=GestorSesiones-Setup-{#AppVersion}
SetupIconFile=..\gestor_sesiones\recursos\icono.ico
UninstallDisplayIcon={app}\GestorSesiones.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\GestorSesiones.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\MANUAL_USUARIO.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\mis_cuentas.ejemplo.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\GestorSesiones.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\GestorSesiones.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GestorSesiones.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
