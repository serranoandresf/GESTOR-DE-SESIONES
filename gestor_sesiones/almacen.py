"""Lectura y escritura de los archivos JSON (un archivo por proyecto y por grupo).

Las escrituras son atómicas (archivo temporal + os.replace) para no corromper
los datos si el programa se cierra a mitad de un guardado.
"""
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


def nombre_seguro(nombre: str) -> str:
    """Convierte un nombre en un nombre de archivo válido en Windows."""
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre).strip().rstrip(".")
    return n.replace(" ", "_") or "sin_nombre"


def _clave_natural(texto: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", texto)]


class Almacen:
    def __init__(self, raiz):
        self.raiz = Path(raiz)
        self.dir_proyectos = self.raiz / "proyectos"
        self.dir_grupos = self.raiz / "grupos"
        self.dir_respaldos = self.raiz / "respaldos"
        for d in (self.dir_proyectos, self.dir_grupos, self.dir_respaldos):
            d.mkdir(parents=True, exist_ok=True)

    # -- utilidades -----------------------------------------------------------
    @staticmethod
    def _leer(ruta: Path):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _escribir(ruta: Path, datos):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_name(ruta.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)

    # -- proyectos ------------------------------------------------------------
    def ruta_proyecto(self, nombre: str) -> Path:
        return self.dir_proyectos / (nombre_seguro(nombre) + ".json")

    def existe_proyecto(self, nombre: str) -> bool:
        return self.ruta_proyecto(nombre).exists()

    def listar_proyectos(self):
        nombres = []
        for p in self.dir_proyectos.glob("*.json"):
            try:
                nombres.append(self._leer(p).get("nombre", p.stem))
            except (json.JSONDecodeError, OSError):
                continue
        return sorted(nombres, key=_clave_natural)

    def cargar_proyecto(self, nombre: str) -> dict:
        return self._leer(self.ruta_proyecto(nombre))

    def guardar_proyecto(self, proyecto: dict):
        self._escribir(self.ruta_proyecto(proyecto["nombre"]), proyecto)

    def respaldar_proyecto(self, nombre: str, conservar: int = 30):
        """Copia el JSON actual a respaldos/ antes de modificar o borrar un proyecto."""
        origen = self.ruta_proyecto(nombre)
        if not origen.exists():
            return None
        marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destino = self.dir_respaldos / f"{nombre_seguro(nombre)}__{marca}.json"
        shutil.copy2(origen, destino)
        previos = sorted(self.dir_respaldos.glob(f"{nombre_seguro(nombre)}__*.json"))
        for viejo in previos[:-conservar]:
            try:
                viejo.unlink()
            except OSError:
                pass
        return destino

    # -- grupos ---------------------------------------------------------------
    def ruta_grupo(self, nombre: str) -> Path:
        return self.dir_grupos / (nombre_seguro(nombre) + ".json")

    def listar_grupos(self):
        nombres = []
        for p in self.dir_grupos.glob("*.json"):
            try:
                nombres.append(self._leer(p).get("nombre", p.stem))
            except (json.JSONDecodeError, OSError):
                continue
        return sorted(nombres, key=_clave_natural)

    def cargar_grupo(self, nombre: str) -> dict:
        return self._leer(self.ruta_grupo(nombre))

    def guardar_grupo(self, grupo: dict):
        self._escribir(self.ruta_grupo(grupo["nombre"]), grupo)
