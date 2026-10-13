"""Reglas de negocio: grupos, correos y proyectos (sin Tkinter, para poder probarlas aisladas).

Qué guarda la app:
  - Grupos de correos (Grupo 1, Grupo 2…) y, dentro de cada uno, los correos (con contraseña opcional).
  - Proyectos: nombre, estado (por empezar, en curso, pausado, completado), de qué se trata, próximo paso, notas
    y el correo con el que se trabajan.

Reglas que se hacen cumplir:
  1. Un proyecto está en UN solo correo; un correo puede tener varios proyectos.
  2. Un correo no puede repetirse (ni dentro de un grupo ni entre grupos).
  3. No se puede quitar un correo que tenga proyectos (se mueven antes).
  4. Las contraseñas (opcionales) se guardan solo cifradas con Windows (DPAPI); nunca en texto plano.
La app no se conecta a ninguna IA ni a internet.
"""
import csv
import os
from datetime import date

from . import secretos as secretos_win

_NADA = object()          # "no cambiar" (None significa «sin correo»)

ESTADOS = ["Por empezar", "En curso", "Pausado", "Completado"]
ESTADO_INICIAL = "En curso"
ICONO_ESTADO = {"Por empezar": "○", "En curso": "●", "Pausado": "⏸", "Completado": "✔"}


def normalizar_estado(texto, defecto=ESTADO_INICIAL):
    """Acepta mayúsculas/minúsculas/acentos y sinónimos comunes; si no lo reconoce devuelve `defecto`."""
    t = (texto or "").strip().lower()
    t = t.translate(str.maketrans("áéíóú", "aeiou"))
    mapa = {"por empezar": "Por empezar", "pendiente": "Por empezar", "nuevo": "Por empezar",
            "en curso": "En curso", "activo": "En curso", "en proceso": "En curso", "en progreso": "En curso",
            "pausado": "Pausado", "en pausa": "Pausado", "detenido": "Pausado",
            "completado": "Completado", "terminado": "Completado", "finalizado": "Completado", "listo": "Completado",
            "hecho": "Completado"}
    return mapa.get(t, defecto)


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
        p["estado"] = normalizar_estado(p.get("estado"))      # los proyectos de versiones anteriores quedan «En curso»
        p.setdefault("proximo_paso", "")
        p.setdefault("actualizado", "")
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

    def resumen(self):
        """Cuenta correos, proyectos y proyectos por estado (para el encabezado)."""
        ind = self.indice()
        por_estado = {e: 0 for e in ESTADOS}
        for p in ind["proyectos"].values():
            por_estado[p["estado"]] += 1
        return {"correos": sum(len(c) for _, c in ind["grupos"]), "proyectos": len(ind["proyectos"]),
                "por_estado": por_estado, "sin_correo": len(ind["sin_correo"]),
                "correos_libres": sum(1 for _, cs in ind["grupos"] for c in cs if c["correo"].lower() not in ind["por_correo"])}

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
    @staticmethod
    def _validar_estado(estado):
        if estado not in ESTADOS:
            raise ErrorRegla("El estado debe ser uno de: " + ", ".join(ESTADOS) + ".")
        return estado

    def crear_proyecto(self, nombre: str, descripcion: str = "", correo: str | None = None, notas: str = "",
                       estado: str = ESTADO_INICIAL, proximo_paso: str = ""):
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
        p = {"nombre": nombre, "descripcion": descripcion.strip(), "notas": notas.strip(), "correo": correo or None,
             "estado": self._validar_estado(estado), "proximo_paso": (proximo_paso or "").strip(),
             "actualizado": date.today().isoformat()}
        self.alm.guardar_proyecto(p)
        return p

    def actualizar_proyecto(self, nombre: str, nuevo_nombre: str | None = None, descripcion: str | None = None,
                            notas: str | None = None, correo=_NADA, estado: str | None = None,
                            proximo_paso: str | None = None):
        """Cambia nombre, estado, descripción, próximo paso, notas y/o correo (correo=None lo deja sin correo).
        Valida todo antes de escribir y anota la fecha de la última actualización."""
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
        if estado is not None:
            p["estado"] = self._validar_estado(estado)
        if proximo_paso is not None:
            p["proximo_paso"] = proximo_paso.strip()
        if descripcion is not None:
            p["descripcion"] = descripcion.strip()
        if notas is not None:
            p["notas"] = notas.strip()
        p["actualizado"] = date.today().isoformat()
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
        """Una fila por proyecto (y una por correo sin proyectos): Grupo, Correo, Proyecto, Estado, De qué se trata,
        Próximo paso, Notas."""
        ind = self.indice()
        filas = []
        for gn, cuentas in ind["grupos"]:
            for c in cuentas:
                nombres = ind["por_correo"].get(c["correo"].lower(), [])
                if not nombres:
                    filas.append([gn, c["correo"], "", "", "", "", ""])
                for pn in nombres:
                    p = ind["proyectos"][pn]
                    filas.append([gn, c["correo"], pn, p["estado"], p["descripcion"], p["proximo_paso"], p["notas"]])
        for pn in ind["sin_correo"]:
            p = ind["proyectos"][pn]
            filas.append(["", "", pn, p["estado"], p["descripcion"], p["proximo_paso"], p["notas"]])
        return filas

    def exportar_csv(self, ruta):
        """CSV con ';' y UTF-8 con BOM: se abre directo en Excel (configuración regional en español)."""
        with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Grupo", "Correo", "Proyecto", "Estado", "De qué se trata", "Próximo paso", "Notas"])
            w.writerows(self.filas_lista())

    def importar_csv(self, ruta):
        """Carga la lista exportada (Grupo;Correo;Proyecto;De qué se trata;Notas). Seguro de repetir:
        crea lo que falta, no duplica y no borra nada. Devuelve (correos_nuevos, proyectos_nuevos, proyectos_actualizados)."""
        try:
            with open(ruta, encoding="utf-8-sig", newline="") as f:
                muestra = f.readline()
                f.seek(0)
                sep = ";" if muestra.count(";") >= muestra.count(",") else ","
                filas = list(csv.reader(f, delimiter=sep))
        except OSError as e:
            raise ErrorRegla(f"No pude leer el archivo: {e}")
        if len(filas) < 2:
            raise ErrorRegla("El archivo está vacío.")
        enc = [x.strip().lower() for x in filas[0]]

        def col(prefijo):
            return next((i for i, x in enumerate(enc) if x.startswith(prefijo)), -1)
        iG, iC, iP, iD, iN = col("grupo"), col("correo"), col("proyecto"), col("de qu"), col("notas")
        iE, iS = col("estado"), next((i for i, x in enumerate(enc) if x.replace("ó", "o").startswith("proximo")), -1)
        if iC < 0 or iP < 0:
            raise ErrorRegla("No parece la lista exportada: faltan las columnas Correo y Proyecto.")
        get = lambda r, i: (r[i].strip() if 0 <= i < len(r) else "")
        nuevos_c = nuevos_p = actualizados = 0
        for r in filas[1:]:
            g, c, p = get(r, iG), get(r, iC), get(r, iP)
            if c:
                g = g or "Sin grupo"
                if g not in self.grupos():
                    self.crear_grupo(g)
                if not self.buscar_cuenta(c):
                    self.agregar_cuenta(g, c)
                    nuevos_c += 1
            if not p:
                continue
            d, n, paso = get(r, iD), get(r, iN), get(r, iS)
            est = get(r, iE)
            if self.alm.existe_proyecto(p):
                actual = self.proyecto(p)
                self.actualizar_proyecto(p, descripcion=d or actual.get("descripcion", ""),
                                         notas=n or actual.get("notas", ""), correo=(c or actual.get("correo") or None),
                                         estado=normalizar_estado(est, actual["estado"]) if est else None,
                                         proximo_paso=paso or actual.get("proximo_paso", ""))
                actualizados += 1
            else:
                self.crear_proyecto(p, d, c or None, n, estado=normalizar_estado(est), proximo_paso=paso)
                nuevos_p += 1
        return nuevos_c, nuevos_p, actualizados

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
