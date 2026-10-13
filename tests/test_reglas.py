"""Pruebas de la lógica (sin interfaz). Ejecutar:  py -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gestor_sesiones import cuentas_lote as cl
from gestor_sesiones.almacen import Almacen
from gestor_sesiones.config import Config
from gestor_sesiones.ejemplo import crear_datos_ejemplo
from gestor_sesiones.reglas import ErrorRegla, Servicio


class FakeSecretos:
    """Sustituto de DPAPI para probar en Linux: NO cifra, solo simula proteger/desproteger."""
    def proteger(self, t):
        return "enc:" + t[::-1]

    def desproteger(self, b):
        if not b.startswith("enc:"):
            raise ValueError("dato ajeno")
        return b[4:][::-1]


A, B = "cuenta1a@ejemplo.com", "cuenta2a@ejemplo.com"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Servicio(Almacen(Path(self.tmp.name) / "datos"), None, secretos=FakeSecretos())
        crear_datos_ejemplo(self.s)

    def tearDown(self):
        self.tmp.cleanup()


class TestCorreos(Base):
    def test_ejemplo_crea_grupos_y_proyectos(self):
        self.assertEqual(self.s.grupos(), ["Grupo 1", "Grupo 2"])
        self.assertEqual(self.s.proyectos_de(A), ["Curso de inglés", "Tienda online"])
        self.assertEqual(self.s.verificar_reglas(), [])

    def test_agregar_y_duplicados(self):
        self.s.agregar_cuenta("Grupo 1", "nuevo@gmail.com")
        with self.assertRaises(ErrorRegla):
            self.s.agregar_cuenta("Grupo 2", "NUEVO@gmail.com")        # repetido entre grupos
        with self.assertRaises(ErrorRegla):
            self.s.agregar_cuenta("Grupo 1", "sin-arroba")

    def test_clave_protegida_y_nunca_en_claro(self):
        self.s.agregar_cuenta("Grupo 1", "real@gmail.com", "S3creta!")
        c = next(c for c in self.s.grupo("Grupo 1")["cuentas"] if c["correo"] == "real@gmail.com")
        self.assertTrue(self.s.tiene_clave(c))
        self.assertEqual(self.s.obtener_clave("Grupo 1", "real@gmail.com"), "S3creta!")
        self.assertNotIn("S3creta!", self.s.alm.ruta_grupo("Grupo 1").read_text(encoding="utf-8"))
        self.assertIsNone(self.s.obtener_clave("Grupo 1", A))

    def test_editar_correo_conserva_clave_y_arrastra_proyectos(self):
        self.s.agregar_cuenta("Grupo 1", "a@x.com", "clave1")
        self.s.crear_proyecto("P", correo="a@x.com")
        self.s.editar_cuenta("Grupo 1", "a@x.com", nuevo_correo="b@x.com")
        self.assertEqual(self.s.obtener_clave("Grupo 1", "b@x.com"), "clave1")
        self.assertEqual(self.s.correo_de("P"), "b@x.com")
        self.s.editar_cuenta("Grupo 1", "b@x.com", clave="clave2")
        self.assertEqual(self.s.obtener_clave("Grupo 1", "b@x.com"), "clave2")
        self.s.editar_cuenta("Grupo 1", "b@x.com", quitar_clave=True)
        self.assertIsNone(self.s.obtener_clave("Grupo 1", "b@x.com"))
        self.assertEqual(self.s.verificar_reglas(), [])

    def test_editar_rechaza_duplicado_y_invalido(self):
        with self.assertRaises(ErrorRegla):
            self.s.editar_cuenta("Grupo 1", A, nuevo_correo=B.upper())
        with self.assertRaises(ErrorRegla):
            self.s.editar_cuenta("Grupo 1", A, nuevo_correo="sin-arroba")

    def test_si_falla_la_proteccion_no_guarda_nada(self):
        class Roto:
            def proteger(self, t):
                raise OSError("sin DPAPI")
        self.s.sec = Roto()
        with self.assertRaises(ErrorRegla):
            self.s.agregar_cuenta("Grupo 1", "c@x.com", "pw")
        self.assertNotIn("c@x.com", [c["correo"] for c in self.s.grupo("Grupo 1")["cuentas"]])

    def test_clave_ilegible_da_mensaje_claro(self):
        self.s.agregar_cuenta("Grupo 1", "d@x.com", "pw")
        g = self.s.grupo("Grupo 1")
        next(c for c in g["cuentas"] if c["correo"] == "d@x.com")["clave_protegida"] = "basura"
        self.s.alm.guardar_grupo(g)
        with self.assertRaises(ErrorRegla):
            self.s.obtener_clave("Grupo 1", "d@x.com")

    def test_mover_correo_de_grupo_conserva_clave_y_proyectos(self):
        self.s.editar_cuenta("Grupo 1", A, clave="pw")
        self.s.mover_cuenta("Grupo 1", A, "Grupo 2")
        self.assertNotIn(A, [c["correo"] for c in self.s.grupo("Grupo 1")["cuentas"]])
        self.assertEqual(self.s.obtener_clave("Grupo 2", A), "pw")
        self.assertEqual(len(self.s.proyectos_de(A)), 2)

    def test_quitar_correo_con_proyectos_se_niega(self):
        with self.assertRaises(ErrorRegla):
            self.s.quitar_cuenta("Grupo 1", A)
        self.s.quitar_cuenta("Grupo 1", "cuenta1b@ejemplo.com")      # sin proyectos: sí

    def test_grupos(self):
        self.assertEqual(self.s.crear_grupo()["nombre"], "Grupo 3")
        with self.assertRaises(ErrorRegla):
            self.s.quitar_grupo("Grupo 1")                           # tiene correos
        self.s.quitar_grupo("Grupo 3")
        self.assertNotIn("Grupo 3", self.s.grupos())


class TestProyectos(Base):
    def test_un_correo_varios_proyectos_pero_un_proyecto_un_correo(self):
        self.s.asignar_correo("Bot de trading", A)                   # mover: sale del correo anterior
        self.assertEqual(self.s.proyectos_de(B), [])
        self.assertIn("Bot de trading", self.s.proyectos_de(A))
        self.assertEqual(self.s.correo_de("Bot de trading"), A)

    def test_crear_validaciones(self):
        with self.assertRaises(ErrorRegla):
            self.s.crear_proyecto("  ")
        with self.assertRaises(ErrorRegla):
            self.s.crear_proyecto("Tienda online")                   # repetido
        with self.assertRaises(ErrorRegla):
            self.s.crear_proyecto("X", correo="nadie@x.com")
        self.s.crear_proyecto("Sin correo todavía", "algo")
        self.assertIn("Sin correo todavía", self.s.proyectos_sin_correo())

    def test_asignar_a_correo_inexistente_y_dejar_sin_correo(self):
        with self.assertRaises(ErrorRegla):
            self.s.asignar_correo("Tienda online", "nadie@x.com")
        self.assertEqual(self.s.correo_de("Tienda online"), A)       # no cambió nada
        self.s.asignar_correo("Tienda online", None)
        self.assertIn("Tienda online", self.s.proyectos_sin_correo())

    def test_asignar_ignora_mayusculas(self):
        self.s.asignar_correo("Tienda online", B.upper())
        self.assertEqual(self.s.correo_de("Tienda online"), B)       # queda con la escritura registrada

    def test_actualizar_texto_y_renombrar(self):
        self.s.actualizar_proyecto("Tienda online", nuevo_nombre="Tienda", descripcion="  nueva  ", notas="ojo")
        self.assertNotIn("Tienda online", self.s.proyectos())
        p = self.s.proyecto("Tienda")
        self.assertEqual((p["descripcion"], p["notas"], p["correo"]), ("nueva", "ojo", A))
        with self.assertRaises(ErrorRegla):
            self.s.actualizar_proyecto("Tienda", nuevo_nombre="Curso de inglés")   # ya existe
        self.assertEqual(self.s.proyecto("Tienda")["descripcion"], "nueva")        # nada a medias
        self.assertFalse((self.s.alm.dir_proyectos / "Tienda_online.json").exists())

    def test_cambiar_solo_mayusculas_del_nombre(self):
        self.s.actualizar_proyecto("Tienda online", nuevo_nombre="TIENDA ONLINE")
        self.assertEqual(self.s.proyectos().count("TIENDA ONLINE"), 1)
        self.assertNotIn("Tienda online", self.s.proyectos())

    def test_quitar_proyecto_deja_respaldo(self):
        self.s.quitar_proyecto("Bot de trading")
        self.assertNotIn("Bot de trading", self.s.proyectos())
        self.assertTrue(list(self.s.alm.dir_respaldos.glob("Bot_de_trading__*.json")))

    def test_correo_huerfano_se_avisa_y_va_a_sin_correo(self):
        g = self.s.grupo("Grupo 2")
        g["cuentas"] = [c for c in g["cuentas"] if c["correo"] != B]
        self.s.alm.guardar_grupo(g)
        self.assertTrue(any("Bot de trading" in a for a in self.s.verificar_reglas()))
        self.assertIn("Bot de trading", self.s.indice()["sin_correo"])


class TestIndiceYExportar(Base):
    def test_indice(self):
        ind = self.s.indice()
        self.assertEqual(ind["por_correo"][A.lower()], ["Curso de inglés", "Tienda online"])
        self.assertEqual(ind["sin_correo"], [])
        self.assertEqual([g for g, _ in ind["grupos"]], ["Grupo 1", "Grupo 2"])

    def test_csv(self):
        self.s.crear_proyecto("Suelto", "sin correo")
        ruta = Path(self.tmp.name) / "lista.csv"
        self.s.exportar_csv(ruta)
        txt = ruta.read_bytes()
        self.assertTrue(txt.startswith(b"\xef\xbb\xbf"))             # BOM para Excel
        lineas = txt.decode("utf-8-sig").splitlines()
        self.assertEqual(lineas[0], "Grupo;Correo;Proyecto;Estado;De qué se trata;Próximo paso;Notas")
        self.assertIn("Grupo 1;cuenta1a@ejemplo.com;Tienda online;En curso;Venta de productos por internet: catálogo, pagos y envíos.;;", lineas)
        self.assertIn("Grupo 1;cuenta1b@ejemplo.com;;;;;", lineas)   # correo sin proyectos
        self.assertIn(";;Suelto;En curso;sin correo;;", lineas)               # proyecto sin correo


class TestLote(Base):
    def test_leer_archivo_valida(self):
        f = Path(self.tmp.name) / "c.json"
        f.write_text('{"_nota": "x", "Grupo 1": ["a@x.com", "b@x.com"]}', encoding="utf-8")
        self.assertEqual(cl.leer_archivo(f), {"Grupo 1": ["a@x.com", "b@x.com"]})
        for malo in ('{"Grupo 1": ["a@x.com", "A@x.com"]}', '{"Grupo 1": ["sin-arroba"]}', "no es json", "[]"):
            f.write_text(malo, encoding="utf-8")
            with self.assertRaises(ErrorRegla):
                cl.leer_archivo(f)

    def test_cargar_reemplaza_ejemplo_conserva_claves_y_no_duplica(self):
        self.s.editar_cuenta("Grupo 1", A, nuevo_correo="mia@gmail.com", clave="pw-guardada")   # ya editada a mano
        grupos = {"Grupo 1": ["uno@x.com"], "Grupo 2": ["mia@gmail.com", "dos@x.com"]}
        quitados, nuevas = cl.cargar(self.s, grupos)
        self.assertEqual((quitados, nuevas), ([], 3))
        self.assertEqual([c["correo"] for c in self.s.grupo("Grupo 1")["cuentas"]], ["uno@x.com"])
        self.assertEqual(self.s.obtener_clave("Grupo 2", "mia@gmail.com"), "pw-guardada")        # se movió con su clave
        self.assertEqual(cl.cargar(self.s, grupos), ([], 0))                                     # repetir no duplica
        self.assertEqual(self.s.verificar_reglas(), [])

    def test_proyectos_de_correos_que_desaparecen_quedan_sin_correo(self):
        cl.cargar(self.s, {"Grupo 1": ["real1@x.com"], "Grupo 2": ["real2@x.com"]})
        self.assertEqual(self.s.proyectos_sin_correo(), ["Bot de trading", "Curso de inglés", "Tienda online"])
        self.assertEqual(self.s.verificar_reglas(), [])

    def test_grupos_con_nombre_anterior_se_reemplazan(self):
        self.s.alm.guardar_grupo({"nombre": cl.LEGADOS[0], "cuentas": [{"correo": "z@x.com", "clave_protegida": "enc:x"}]})
        quitados, _ = cl.cargar(self.s, {"Grupo 1": ["z@x.com"]})
        self.assertIn(cl.LEGADOS[0], quitados)
        self.assertNotIn(cl.LEGADOS[0], self.s.grupos())
        c = self.s.grupo("Grupo 1")["cuentas"][0]
        self.assertEqual((c["correo"], c["clave_protegida"]), ("z@x.com", "enc:x"))

    def test_exportar_sin_claves(self):
        self.s.editar_cuenta("Grupo 1", A, clave="secreta")
        lista = cl.exportar(self.s)
        self.assertNotIn("secreta", str(lista))
        self.assertIn(A, lista["Grupo 1"])


class TestDatosDeVersionesAnteriores(unittest.TestCase):
    """Los archivos de la v1.x (memoria, tareas, sesión activa…) siguen funcionando y no se pierden."""

    def test_proyecto_y_grupo_antiguos(self):
        with tempfile.TemporaryDirectory() as d:
            alm = Almacen(Path(d))
            alm.guardar_proyecto({"nombre": "CIMA", "descripcion": "holding", "correo": "a@x.com",
                                  "memoria": {"notas": "importante"}, "tareas": [{"id": "T-001"}],
                                  "historial_sesiones": [{"fecha": "2026-10-10"}]})
            alm.guardar_grupo({"nombre": "Grupo 1", "estado": "en sesión", "proyecto_tarea_en_curso": "CIMA / T-001",
                               "cuentas": [{"correo": "a@x.com", "estado": "en uso", "ultimo_uso": "2026-10-10 10:00",
                                            "clave_protegida": "enc:cba"}]})
            (Path(d) / "sesion_activa.json").write_text("{}", encoding="utf-8")
            s = Servicio(alm, None, secretos=FakeSecretos())
            self.assertEqual(s.proyectos_de("a@x.com"), ["CIMA"])
            self.assertEqual(s.obtener_clave("Grupo 1", "a@x.com"), "abc")
            self.assertEqual(s.proyecto("CIMA")["notas"], "")
            s.actualizar_proyecto("CIMA", descripcion="nueva", notas="mis notas")
            p = alm.cargar_proyecto("CIMA")
            self.assertEqual((p["descripcion"], p["notas"]), ("nueva", "mis notas"))
            self.assertEqual(p["memoria"], {"notas": "importante"})              # lo antiguo se conserva
            self.assertEqual(p["historial_sesiones"], [{"fecha": "2026-10-10"}])


class ImportarCsv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Servicio(Almacen(Path(self.tmp.name) / "datos"), None, secretos=FakeSecretos())
        self.csv = Path(self.tmp.name) / "l.csv"
        self.csv.write_text("\ufeffGrupo;Correo;Proyecto;De qué se trata;Notas\n"
                            "Grupo A;a@x.com;UNO;Tema uno;\nGrupo A;b@x.com;;;\nGrupo B;c@x.com;DOS;;n\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_importa_y_es_repetible(self):
        self.assertEqual(self.s.importar_csv(self.csv), (3, 2, 0))
        self.assertEqual(self.s.correo_de("UNO"), "a@x.com")
        self.assertEqual(self.s.proyecto("UNO")["descripcion"], "Tema uno")
        self.assertEqual(self.s.importar_csv(self.csv), (0, 0, 2))
        self.assertEqual(len(self.s.proyectos()), 2)

    def test_archivo_ajeno(self):
        self.csv.write_text("a;b\n1;2\n", encoding="utf-8")
        with self.assertRaises(ErrorRegla):
            self.s.importar_csv(self.csv)


class Estados(Base):
    def test_por_defecto_y_cambio(self):
        self.assertEqual(self.s.proyecto("Tienda online")["estado"], "En curso")
        self.s.actualizar_proyecto("Tienda online", estado="Completado", proximo_paso="  Cobrar la factura ")
        p = self.s.proyecto("Tienda online")
        self.assertEqual((p["estado"], p["proximo_paso"]), ("Completado", "Cobrar la factura"))
        self.assertTrue(p["actualizado"])
        self.assertEqual(self.s.resumen()["por_estado"]["Completado"], 1)

    def test_estado_invalido(self):
        with self.assertRaises(ErrorRegla):
            self.s.actualizar_proyecto("Tienda online", estado="Quien sabe")
        with self.assertRaises(ErrorRegla):
            self.s.crear_proyecto("Nuevo", estado="x")

    def test_proyecto_antiguo_sin_estado(self):
        p = self.s.alm.cargar_proyecto("Tienda online")
        p.pop("estado", None)
        self.s.alm.guardar_proyecto(p)
        self.assertEqual(self.s.proyecto("Tienda online")["estado"], "En curso")

    def test_normalizar(self):
        from gestor_sesiones.reglas import normalizar_estado as n
        self.assertEqual(n(" TERMINADO "), "Completado")
        self.assertEqual(n("en pausa"), "Pausado")
        self.assertEqual(n("", "Pausado"), "Pausado")

    def test_csv_ida_y_vuelta(self):
        self.s.actualizar_proyecto("Tienda online", estado="Pausado", proximo_paso="Elegir pasarela")
        ruta = Path(self.tmp.name) / "l.csv"
        self.s.exportar_csv(ruta)
        otro = Servicio(Almacen(Path(self.tmp.name) / "otro"), None, secretos=FakeSecretos())
        otro.importar_csv(ruta)
        p = otro.proyecto("Tienda online")
        self.assertEqual((p["estado"], p["proximo_paso"]), ("Pausado", "Elegir pasarela"))


if __name__ == "__main__":
    unittest.main()
