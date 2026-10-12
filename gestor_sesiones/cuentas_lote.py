"""Carga y exportación de correos por lotes (solo correos, nunca contraseñas).

Formato del archivo (.json):  {"Grupo 1": ["a@gmail.com", "b@gmail.com"], "Grupo 2": [...]}
"""
import json
import re
from pathlib import Path

from .reglas import ErrorRegla

# Nombres que usó una versión anterior del cargador: si existen, se reemplazan por los del archivo.
LEGADOS = ["1 - Núcleo", "2 - Hongos y micología", "3 - Agricultura, inversión y empresas", "4 - Proyectos en desarrollo"]


def leer_archivo(ruta) -> dict:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ErrorRegla(f"No pude leer el archivo de correos: {e}")
    if not isinstance(datos, dict) or not datos:
        raise ErrorRegla('El archivo debe tener la forma {"Grupo 1": ["correo1", "correo2"], "Grupo 2": [...]}.')
    limpio, vistos = {}, set()
    for grupo, correos in datos.items():
        if grupo.startswith("_"):
            continue                                   # claves de comentario, p. ej. "_nota"
        if not isinstance(correos, list):
            raise ErrorRegla(f"«{grupo}» debe ser una lista de correos.")
        lista = []
        for c in correos:
            c = str(c).strip()
            if "@" not in c or " " in c:
                raise ErrorRegla(f"Correo no válido en «{grupo}»: {c!r}")
            if c.lower() in vistos:
                raise ErrorRegla(f"El correo {c} aparece repetido en el archivo.")
            vistos.add(c.lower())
            lista.append(c)
        limpio[str(grupo).strip()] = lista
    if not limpio:
        raise ErrorRegla("El archivo no tiene grupos.")
    return limpio


def exportar(srv) -> dict:
    """{grupo: [correos]} de lo que hay registrado (sin contraseñas)."""
    return {gn: [c["correo"] for c in srv.grupo(gn)["cuentas"]] for gn in srv.grupos()}


def cargar(srv, grupos: dict, confirmar=None):
    """Crea/actualiza los grupos indicados. Devuelve (grupos_quitados, correos_nuevos), o None si se cancela.

    - Quita los correos @ejemplo.com y los que pertenecen a otro grupo del archivo (se mueven con su contraseña).
    - No duplica ni borra correos desconocidos. Seguro de repetir.
    - Los proyectos cuyo correo ya no existe quedan «sin correo» (no se pierden).
    """
    existentes = srv.grupos()
    previas = {}
    for gn in existentes:
        for c in srv.grupo(gn)["cuentas"]:
            previas[c["correo"].lower()] = c
    quitar = [gn for gn in existentes if gn in LEGADOS or (re.fullmatch(r"Grupo \d+", gn) and gn not in grupos)]
    if confirmar and not confirmar(quitar):
        return None
    nuevas = 0
    for nombre, correos in grupos.items():
        g = srv.grupo(nombre) if nombre in existentes else {"nombre": nombre, "cuentas": []}
        propios = {x.lower() for x in correos}
        ajenos = {x.lower() for n2, lista in grupos.items() if n2 != nombre for x in lista}
        g["cuentas"] = [c for c in g["cuentas"] if c["correo"].lower() in propios or
                        not (c["correo"].lower().endswith("@ejemplo.com") or c["correo"].lower() in ajenos)]
        ya = {c["correo"].lower() for c in g["cuentas"]}
        for correo in correos:
            if correo.lower() in ya:
                continue
            c = {k: v for k, v in (previas.get(correo.lower()) or {}).items() if k != "correo"}
            g["cuentas"].append({"correo": correo, **c})
            nuevas += 1
        srv.alm.guardar_grupo(g)
    for gn in quitar:
        srv.alm.ruta_grupo(gn).unlink(missing_ok=True)
    for pn in srv.proyectos():                          # correos que ya no existen
        p = srv.proyecto(pn)
        if p.get("correo") and not srv.buscar_cuenta(p["correo"]):
            p["correo"] = None
            srv.alm.guardar_proyecto(p)
    return quitar, nuevas
