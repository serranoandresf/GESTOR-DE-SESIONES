"""Configuración de la aplicación (solo la carpeta de datos).

Vive en %APPDATA%\\GestorSesiones\\config.json (Windows) y no contiene ningún dato sensible.
"""
import json
import os
from pathlib import Path

APP_NOMBRE = "GestorSesiones"

DEFECTOS = {
    "ruta_datos": "",            # carpeta donde viven proyectos/ y grupos/
}


def carpeta_config() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    p = Path(base) / APP_NOMBRE
    p.mkdir(parents=True, exist_ok=True)
    return p


def ruta_datos_por_defecto() -> str:
    """Usa D:\\Javier\\Documents\\SISTEMA_DE_TRABAJO\\DATOS si existe esa unidad; si no, Documentos del usuario."""
    d = Path("D:/Javier/Documents")
    if d.exists():
        return str(d / "SISTEMA_DE_TRABAJO" / "DATOS")
    return str(Path.home() / "Documents" / "SISTEMA_DE_TRABAJO" / "DATOS")


class Config:
    def __init__(self, ruta_archivo: Path | None = None):
        self.ruta_archivo = Path(ruta_archivo) if ruta_archivo else carpeta_config() / "config.json"
        self.datos = dict(DEFECTOS)
        self.cargar()
        if not self.datos.get("ruta_datos"):
            self.datos["ruta_datos"] = ruta_datos_por_defecto()

    def __getitem__(self, k):
        return self.datos[k]

    def __setitem__(self, k, v):
        self.datos[k] = v

    def cargar(self):
        """Lee el archivo; ignora las opciones antiguas (temporizador, sonido, URL de la IA) que ya no existen."""
        try:
            with open(self.ruta_archivo, "r", encoding="utf-8") as f:
                leido = json.load(f)
            for k in DEFECTOS:
                if k in leido:
                    self.datos[k] = leido[k]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def guardar(self):
        try:
            self.ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.ruta_archivo.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.ruta_archivo)
        except OSError:
            pass
