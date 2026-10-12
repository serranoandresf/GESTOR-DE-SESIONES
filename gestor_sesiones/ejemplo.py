"""Datos de ejemplo para practicar: 2 grupos con correos ficticios (@ejemplo.com) y 3 proyectos."""


def crear_datos_ejemplo(servicio):
    for n in (1, 2):
        nombre = f"Grupo {n}"
        if nombre not in servicio.grupos():
            servicio.alm.guardar_grupo({"nombre": nombre, "cuentas": [
                {"correo": f"cuenta{n}a@ejemplo.com"}, {"correo": f"cuenta{n}b@ejemplo.com"}]})
    ejemplos = [
        ("Tienda online", "Venta de productos por internet: catálogo, pagos y envíos.", "cuenta1a@ejemplo.com"),
        ("Curso de inglés", "Plataforma gratuita de inglés A1–C2.", "cuenta1a@ejemplo.com"),
        ("Bot de trading", "Pruebas de estrategias en MetaTrader 5.", "cuenta2a@ejemplo.com"),
    ]
    for nombre, desc, correo in ejemplos:
        if not servicio.alm.existe_proyecto(nombre):
            servicio.crear_proyecto(nombre, desc, correo)
