"""Carga tus cuentas desde mis_cuentas.json (junto a este script, o la ruta que pases como argumento).

Uso (PowerShell, dentro de la carpeta de la app):   py cargar_cuentas.py [archivo.json]

- Seguro de repetir: no duplica cuentas y conserva las contraseñas ya guardadas.
- No toca tus proyectos (los que se queden sin correo pasan a «Sin correo asignado»).
- Las contraseñas se ponen dentro de la app (👥 Gestionar correos → 🔑 Poner contraseñas en serie).
- También puedes hacerlo desde la app: 👥 Gestionar correos → 📥 Cargar correos desde archivo.
"""
import sys
from pathlib import Path

from gestor_sesiones import cuentas_lote
from gestor_sesiones.almacen import Almacen
from gestor_sesiones.config import Config
from gestor_sesiones.reglas import ErrorRegla, Servicio


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "mis_cuentas.json"
    cfg = Config()
    srv = Servicio(Almacen(cfg["ruta_datos"]), cfg)
    print(f"Carpeta de datos: {cfg['ruta_datos']}\nArchivo de cuentas: {ruta}")
    try:
        grupos = cuentas_lote.leer_archivo(ruta)

        def confirmar(quitar):
            if quitar:
                print("Se quitarán los grupos con nombre anterior: " + ", ".join(quitar))
            print("Se crearán/actualizarán: " + ", ".join(f"{g} ({len(c)})" for g, c in grupos.items()))
            return input("¿Continuar? (s/n): ").strip().lower() in ("s", "si", "sí", "y")

        r = cuentas_lote.cargar(srv, grupos, confirmar)
    except ErrorRegla as e:
        print("\n⚠ " + str(e))
        sys.exit(1)
    if r is None:
        print("Cancelado. No se cambió nada.")
        return
    print(f"\n✅ Listo: {r[1]} cuenta(s) nueva(s). Abre la app → 👥 Gestionar correos → «🔑 Poner contraseñas en serie».")


if __name__ == "__main__":
    main()
