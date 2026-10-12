"""Reglas de negocio: grupos, correos y proyectos (sin Tkinter, para poder probarlas aisladas).

Qué guarda la app:
  - Grupos de correos (Grupo 1, Grupo 2…) y, dentro de cada uno, los correos (con contraseña opcional).
  - Proyectos: nombre, de qué se trata, notas y el correo con el que se trabajan.

Reglas que se hacen cumplir:
  1. Un proyecto está en UN solo correo; un correo puede tener varios proyectos.
  2. Un correo no puede repetirse (ni dentro de un grupo ni entre grupos).
  3. No se puede quitar un correo que tenga proyectos (se mueven antes).
  4. Las contraseñas (opcionales) se guardan solo cifradas con Windows (DPAPI); nunca en texto plano.
La app no se conecta a ninguna IA ni a internet.
"""
import csv
import os

from . import secretos as secretos_win

_NADA = object()          # "no cambiar" (None significa «sin correo»)


class ErrorRegla(Exception):
    """Se intentó algo que rompe una regla. El mensaje está en español, listo para mostrarse."""


class Servicio:
    def __init__(self, almacen, config=None, secretos=None):
        self.alm = almacen
        self.cfg = config
        self.sec = secretos or secretos_win

    # ------------------------------------------------------------ lectura
    def hay_datos(self) -> bool:
        return bool(self.alm.listar_proyectos() or self.alm.listar_grupos())

    def grupos(self):
        return self.alm.listar_grupos()

    def grupo(self, nombre):
        g = self.alm.cargar_grupo(nombre)
        g.setdefault("cuentas", [])
        return g

    def proyectos(self):
        return self.alm.listar_proyectos()

    def proyecto(self, nombre):
        p = self.alm.cargar_proyecto(nombre)
        p.setdefault("descripcion", "")
        p.setdefault("notas", "")
        p.setdefault("correo", None)
        return p

    def indice(self):
        """Lee todo una sola vez (para pintar la lista sin releer archivos).

        Devuelve {'grupos': [(grupo, [cuenta, ...]), ...], 'proyectos': {nombre: proyecto},
                  'por_correo': {correo_en_minusculas: [nombres]}, 'sin_correo': [nombres]}
        """
        grupos = [(gn, self.grupo(gn)["cuentas"]) for gn in self.grupos()]
        registrados = {c["correo"].lower() for _, cuentas in grupos for c in cuentas}
        proyectos, por_correo, sin_correo = {}, {}, []
        for pn in self.proyectos():
            p = self.proyecto(pn)
            proyectos[pn] = p
            co = (p.get("correo") or "").lower()
            if co and co in registrados:
                por_correo.setdefault(co, []).append(pn)
            else:
                sin_correo.append(pn)
        return {"grupos": grupos, "proyectos": proyectos, "por_correo": por_correo, "sin_correo": sin_correo}

    def buscar_cuenta(self, correo: str):
        """(nombre_grupo, cuenta) del correo, o None. Sin distinguir mayúsculas."""
        if not correo:
            return None
        for gn in self.grupos():
            for c in self.grupo(gn)["cuentas"]:
                if c["correo"].lower() == correo.lower():
                    return gn, c
        return None

    def correo_de(self, proyecto: str) -> str | None:
        return self.proyecto(proyecto).get("correo") or None

    def proyectos_de(self, correo: str):
        """Nombres de los proyectos de ese correo."""
        return [pn for pn in self.proyectos() if (self.correo_de(pn) or "").lower() == (correo or "").lower()]

    def proyectos_sin_correo(self):
        return self.indice()["sin_correo"]

    # ---------------------------------------------------- grupos y correos
    def crear_grupo(self, nombre: str | None = None):
        existentes = self.grupos()
        if not nombre:
            n = 1
            while f"Grupo {n}" in existentes:
                n += 1
            nombre = f"Grupo {n}"
        nombre = nombre.strip()
        if nombre in existentes:
            raise ErrorRegla(f"Ya existe «{nombre}».")
        g = {"nombre": nombre, "cuentas": []}
        self.alm.guardar_grupo(g)
        return g

    def quitar_grupo(self, grupo: str):
        if self.grupo(grupo)["cuentas"]:
            raise ErrorRegla(f"«{grupo}» todavía tiene correos. Muévelos a otro grupo o quítalos primero.")
        self.alm.ruta_grupo(grupo).unlink(missing_ok=True)

    @staticmethod
    def _validar_correo(correo: str) -> str:
        correo = (correo or "").strip()
        if "@" not in correo or " " in correo:
            raise ErrorRegla("Escribe un correo válido (por ejemplo nombre@gmail.com).")
        return correo

    def _correo_repetido(self, correo: str, excepto=None):
        for gn in self.grupos():
            for c in self.grupo(gn)["cuentas"]:
                if c["correo"].lower() == correo.lower() and (gn, c["correo"]) != excepto:
                    return gn
        return None

    def _proteger(self, clave: str) -> str:
        """Cifra con Windows y comprueba que se puede leer de vuelta; si no, no se guarda nada."""
        try:
            blob = self.sec.proteger(clave)
            if self.sec.desproteger(blob) != clave:
                raise ValueError("la verificación no coincide")
            return blob
        except Exception as e:
            raise ErrorRegla("No pude proteger la contraseña con Windows, así que NO se guardó "
                             f"(detalle: {e}). El correo sí puede registrarse sin contraseña.")

    def agregar_cuenta(self, grupo: str, correo: str, clave: str | None = None):
        correo = self._validar_correo(correo)
        donde = self._correo_repetido(correo)
        if donde:
            raise ErrorRegla(f"{correo} ya está registrado en {donde}.")
        c = {"correo": correo}
        if clave:
            c["clave_protegida"] = self._proteger(clave)
        g = self.grupo(grupo)
        g["cuentas"].append(c)
        self.alm.guardar_grupo(g)

    def editar_cuenta(self, grupo: str, correo: str, nuevo_correo: str | None = None,
                      clave: str | None = None, quitar_clave: bool = False):
        """Cambia el correo y/o la contraseña. clave vacía/None = conservar la actual."""
        g = self.grupo(grupo)
        c = next((c for c in g["cuentas"] if c["correo"] == correo), None)
        if c is None:
            raise ErrorRegla("El correo no existe.")
        nuevo = self._validar_correo(nuevo_correo) if nuevo_correo is not None else correo
        if nuevo != correo:
            donde = self._correo_repetido(nuevo, excepto=(grupo, correo))
            if donde:
                raise ErrorRegla(f"{nuevo} ya está registrado en {donde}.")
        protegida = self._proteger(clave) if clave else None      # si falla, no se toca nada
        c["correo"] = nuevo
        if quitar_clave:
            c.pop("clave_protegida", None)
        if protegida:
            c["clave_protegida"] = protegida
        self.alm.guardar_grupo(g)
        if nuevo != correo:                                        # sus proyectos lo siguen
            for pn in self.proyectos_de(correo):
                p = self.proyecto(pn)
                p["correo"] = nuevo
                self.alm.guardar_proyecto(p)

    def mover_cuenta(self, grupo: str, correo: str, destino: str):
        if grupo == destino:
            return
        g, d = self.grupo(grupo), self.grupo(destino)
        c = next((c for c in g["cuentas"] if c["correo"] == correo), None)
        if c is None:
            raise ErrorRegla("El correo no existe.")
        g["cuentas"] = [x for x in g["cuentas"] if x is not c]
        d["cuentas"].append(c)
        self.alm.guardar_grupo(d)          # primero el destino: si algo falla, el correo no se pierde
        self.alm.guardar_grupo(g)

    def quitar_cuenta(self, grupo: str, correo: str):
        asignados = self.proyectos_de(correo)
        if asignados:
            raise ErrorRegla(f"{correo} tiene proyectos ({', '.join(asignados)}). "
                             "Muévelos a otro correo (o déjalos sin correo) antes de quitarlo.")
        g = self.grupo(grupo)
        g["cuentas"] = [c for c in g["cuentas"] if c["correo"] != correo]
        self.alm.guardar_grupo(g)

    def tiene_clave(self, cuenta: dict) -> bool:
        return bool(cuenta.get("clave_protegida"))

    def obtener_clave(self, grupo: str, correo: str) -> str | None:
        """Descifra la contraseña (solo para copiarla al portapapeles). None si no tiene."""
        c = next((c for c in self.grupo(grupo)["cuentas"] if c["correo"] == correo), None)
        if c is None:
            raise ErrorRegla("El correo no existe.")
        if not c.get("clave_protegida"):
            return None
        try:
            return self.sec.desproteger(c["clave_protegida"])
        except Exception:
            raise ErrorRegla("No pude leer la contraseña de ese correo (se guardó con otro usuario o PC de Windows, "
                             "o el dato está dañado). Escríbela de nuevo con ✏ Editar correo.")

    # ------------------------------------------------------------ proyectos
    def crear_proyecto(self, nombre: str, descripcion: str = "", correo: str | None = None, notas: str = ""):
        nombre = nombre.strip()
        if not nombre:
            raise ErrorRegla("El proyecto necesita un nombre.")
        if self.alm.existe_proyecto(nombre):
            raise ErrorRegla(f"Ya existe un proyecto llamado «{nombre}».")
        if correo:
            hallado = self.buscar_cuenta(correo)
            if not hallado:
                raise ErrorRegla(f"{correo} no está registrado en tus correos.")
            correo = hallado[1]["correo"]
        p = {"nombre": nombre, "descripcion": descripcion.strip(), "notas": notas.strip(), "correo": correo or None}
        self.alm.guardar_proyecto(p)
        return p

    def actualizar_proyecto(self, nombre: str, nuevo_nombre: str | None = None, descripcion: str | None = None,
                            notas: str | None = None, correo=_NADA):
        """Cambia nombre, descripción, notas y/o correo (correo=None lo deja sin correo). Valida todo antes de escribir."""
        p = self.proyecto(nombre)
        nuevo = (nuevo_nombre if nuevo_nombre is not None else nombre).strip()
        if not nuevo:
            raise ErrorRegla("El proyecto necesita un nombre.")
        if nuevo.lower() != nombre.lower() and self.alm.existe_proyecto(nuevo):
            raise ErrorRegla(f"Ya existe un proyecto llamado «{nuevo}».")
        if correo is not _NADA:
            if correo:
                hallado = self.buscar_cuenta(correo)
                if not hallado:
                    raise ErrorRegla(f"{correo} no está registrado en tus correos.")
                correo = hallado[1]["correo"]
            p["correo"] = correo or None
        if descripcion is not None:
            p["descripcion"] = descripcion.strip()
        if notas is not None:
            p["notas"] = notas.strip()
        self.alm.respaldar_proyecto(nombre)
        p["nombre"] = nuevo
        viejo = self.alm.ruta_proyecto(nombre)
        self.alm.guardar_proyecto(p)
        nuevo_ruta = self.alm.ruta_proyecto(nuevo)
        if viejo.exists() and nuevo_ruta.exists() and not os.path.samefile(viejo, nuevo_ruta):
            viejo.unlink()
        return p

    def asignar_correo(self, proyecto: str, correo: str | None):
        """Pasa el proyecto a UN correo (o lo deja sin correo con None). Nunca queda en dos."""
        return self.actualizar_proyecto(proyecto, correo=correo)

    def quitar_proyecto(self, nombre: str):
        self.alm.respaldar_proyecto(nombre)           # queda una copia en respaldos/
        self.alm.ruta_proyecto(nombre).unlink(missing_ok=True)

    # ------------------------------------------------------------- exportar
    def filas_lista(self):
        """Una fila por proyecto (y una por correo sin proyectos): Grupo, Correo, Proyecto, De qué se trata, Notas."""
        ind = self.indice()
        filas = []
        for gn, cuentas in ind["grupos"]:
            for c in cuentas:
                nombres = ind["por_correo"].get(c["correo"].lower(), [])
                if not nombres:
                    filas.append([gn, c["correo"], "", "", ""])
                for pn in nombres:
                    p = ind["proyectos"][pn]
                    filas.append([gn, c["correo"], pn, p["descripcion"], p["notas"]])
        for pn in ind["sin_correo"]:
            p = ind["proyectos"][pn]
            filas.append(["", "", pn, p["descripcion"], p["notas"]])
        return filas

    def exportar_csv(self, ruta):
        """CSV con ';' y UTF-8 con BOM: se abre directo en Excel (configuración regional en español)."""
        with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Grupo", "Correo", "Proyecto", "De qué se trata", "Notas"])
            w.writerows(self.filas_lista())

    # ------------------------------------------------------------ integridad
    def verificar_reglas(self):
        """Revisa que los archivos cumplan las reglas (por si se editaron a mano). Devuelve avisos."""
        avisos, vistos = [], {}
        for gn in self.grupos():
            for c in self.grupo(gn)["cuentas"]:
                k = c["correo"].lower()
                if k in vistos:
                    avisos.append(f"{c['correo']} está repetido ({vistos[k]} y {gn}).")
                vistos[k] = gn
        for pn in self.proyectos():
            co = self.correo_de(pn)
            if co and co.lower() not in vistos:
                avisos.append(f"{pn}: su correo ({co}) ya no está registrado en tus correos.")
        return avisos
