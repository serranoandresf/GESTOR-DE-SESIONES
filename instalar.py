"""Instala el Gestor de Sesiones para el usuario actual (no pide permisos de administrador).

- Copia la app a  %LOCALAPPDATA%\\Programs\\GestorSesiones
- Crea accesos directos con icono en el Escritorio y en el menú Inicio
- La registra en «Aplicaciones instaladas» de Windows (se puede desinstalar desde ahí)
Es seguro repetirlo para ACTUALIZAR: no toca tus datos (proyectos, grupos, contraseñas).
"""
import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
NOMBRE = "Gestor de Sesiones"
CLAVE_REG = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GestorSesiones"
ARCHIVOS = ["main.py", "README.md", "MANUAL_USUARIO.md", "cargar_cuentas.py", "mis_cuentas.json",
            "mis_cuentas.ejemplo.json", "Desinstalar.bat"]


def destino() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / "GestorSesiones"


def copiar_app(origen: Path, dest: Path):
    """Copia la app; reemplaza el código anterior (gestor_sesiones/) pero no toca nada fuera de la carpeta de la app."""
    dest.mkdir(parents=True, exist_ok=True)
    viejo = dest / "gestor_sesiones"
    if viejo.exists():
        shutil.rmtree(viejo)
    shutil.copytree(origen / "gestor_sesiones", viejo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for nombre in ARCHIVOS:
        if (origen / nombre).exists():
            shutil.copy2(origen / nombre, dest / nombre)


def _ps(script: str):
    cod = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", cod],
                   check=True, capture_output=True)


def crear_accesos(dest: Path, pythonw: str):
    icono = dest / "gestor_sesiones" / "recursos" / "icono.ico"
    q = lambda s: str(s).replace("'", "''")
    _ps(f"""
$w = New-Object -ComObject WScript.Shell
$destinos = @(
  (Join-Path ([Environment]::GetFolderPath('Desktop')) '{NOMBRE}.lnk'),
  (Join-Path ([Environment]::GetFolderPath('Programs')) '{NOMBRE}.lnk')
)
foreach ($d in $destinos) {{
  $s = $w.CreateShortcut($d)
  $s.TargetPath = '{q(pythonw)}'
  $s.Arguments = '"{q(dest / "main.py")}"'
  $s.WorkingDirectory = '{q(dest)}'
  $s.IconLocation = '{q(icono)},0'
  $s.Description = 'Organizador de correos y proyectos'
  $s.Save()
}}
""")


def registrar_desinstalacion(dest: Path):
    import winreg
    from gestor_sesiones import __version__
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_REG) as k:
        for nombre, valor in [("DisplayName", NOMBRE), ("DisplayVersion", __version__), ("Publisher", "Uso personal"),
                              ("InstallLocation", str(dest)),
                              ("DisplayIcon", str(dest / "gestor_sesiones" / "recursos" / "icono.ico")),
                              ("UninstallString", f'"{dest / "Desinstalar.bat"}"')]:
            winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, valor)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)


def main():
    if sys.platform != "win32":
        sys.exit("Este instalador es para Windows.")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("A este Python le falta tkinter. Reinstala Python marcando «tcl/tk and IDLE».")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        sys.exit(f"No encontré pythonw.exe junto a {sys.executable}.")
    dest = destino()
    print(f"Instalando en: {dest}")
    copiar_app(AQUI, dest)
    crear_accesos(dest, str(pythonw))
    registrar_desinstalacion(dest)
    print(f"\n✅ Instalado. Busca «{NOMBRE}» en el Escritorio o en el menú Inicio.")
    print("   Tus datos (proyectos, grupos, contraseñas) NO se tocan al actualizar ni al desinstalar.")
    print("   Si algún día actualizas o cambias de versión de Python, vuelve a ejecutar Instalar.bat.")


if __name__ == "__main__":
    main()
