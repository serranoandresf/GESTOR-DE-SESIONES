"""Ventanas de diálogo (Tkinter). Todas son modales y devuelven su resultado con .mostrar()."""
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import cuentas_lote
from .reglas import ErrorRegla


class Dialogo(tk.Toplevel):
    def __init__(self, master, titulo):
        super().__init__(master)
        self.title(titulo)
        self.transient(master)
        self.resultado = None
        self.protocol("WM_DELETE_WINDOW", self.cancelar)
        self.bind("<Escape>", lambda e: self.cancelar())

    def mostrar(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + max(0, (m.winfo_width() - self.winfo_reqwidth()) // 2)
        y = m.winfo_rooty() + max(0, (m.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus_set()
        self.wait_window(self)
        return self.resultado

    def aceptar(self, resultado=True):
        self.resultado = resultado
        self.destroy()

    def cancelar(self):
        self.resultado = None
        self.destroy()

    def botones(self, parent, texto_ok="Aceptar", comando_ok=None, texto_cancelar="Cancelar"):
        fila = ttk.Frame(parent)
        ttk.Button(fila, text=texto_cancelar, command=self.cancelar).pack(side="right", padx=(8, 0))
        ttk.Button(fila, text=texto_ok, command=comando_ok or self.aceptar).pack(side="right")
        return fila


def etiqueta_correo(srv, grupo, cuenta, proyectos=None):
    """«correo  (Grupo 1 · 2 proyectos)» para listas desplegables."""
    n = len(proyectos if proyectos is not None else srv.proyectos_de(cuenta["correo"]))
    return f"{cuenta['correo']}  ({grupo} · {n} proyecto{'s' if n != 1 else ''})"


# ---------------------------------------------------------------------------
class ElegirDialog(Dialogo):
    def __init__(self, master, titulo, texto, opciones, defecto=0):
        super().__init__(master, titulo)
        self.opciones = opciones
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=texto, wraplength=420, justify="left").pack(anchor="w", pady=(0, 8))
        self.c = ttk.Combobox(f, values=[o[0] for o in opciones], state="readonly", width=52)
        self.c.current(defecto)
        self.c.pack(fill="x")
        self.botones(f, "Aceptar", lambda: self.aceptar(self.opciones[self.c.current()][1])).pack(anchor="e", pady=(12, 0))


class CuentaDialog(Dialogo):
    """Correo + contraseña opcional (campo oculto). Al editar, clave vacía = conservar la actual.
    Con `grupos` pregunta también en qué grupo va (para correos nuevos)."""

    def __init__(self, master, titulo, correo="", tiene_clave=False, grupos=None, grupo_pre=None):
        super().__init__(master, titulo)
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        self.v_correo = tk.StringVar(value=correo)
        self.v_clave = tk.StringVar()
        self.v_quitar = tk.BooleanVar(value=False)
        self.v_ver = tk.BooleanVar(value=False)
        self.v_grupo = tk.StringVar(value=grupo_pre if grupo_pre in (grupos or []) else (grupos[0] if grupos else ""))
        fila = 0
        if grupos:
            ttk.Label(f, text="Grupo:").grid(row=fila, column=0, sticky="w")
            ttk.Combobox(f, textvariable=self.v_grupo, values=grupos, state="readonly", width=38).grid(
                row=fila, column=1, sticky="ew", padx=(8, 0), pady=3)
            fila += 1
        ttk.Label(f, text="Correo:").grid(row=fila, column=0, sticky="w")
        self.e_correo = ttk.Entry(f, textvariable=self.v_correo, width=40)
        self.e_correo.grid(row=fila, column=1, sticky="ew", padx=(8, 0), pady=3)
        fila += 1
        ttk.Label(f, text="Contraseña:").grid(row=fila, column=0, sticky="w")
        self.e_clave = ttk.Entry(f, textvariable=self.v_clave, show="•", width=40)
        self.e_clave.grid(row=fila, column=1, sticky="ew", padx=(8, 0), pady=3)
        fila += 1
        ttk.Checkbutton(f, text="Mostrar mientras la escribo", variable=self.v_ver,
                        command=lambda: self.e_clave.config(show="" if self.v_ver.get() else "•")
                        ).grid(row=fila, column=1, sticky="w", padx=(8, 0))
        fila += 1
        if tiene_clave:
            ttk.Label(f, foreground="#555", text="Ya tiene una contraseña guardada. Déjala vacía para conservarla.").grid(
                row=fila, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
            ttk.Checkbutton(f, text="Quitar la contraseña guardada", variable=self.v_quitar).grid(
                row=fila + 1, column=1, sticky="w", padx=(8, 0))
            fila += 2
        else:
            ttk.Label(f, foreground="#555", text="La contraseña es opcional.").grid(row=fila, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
            fila += 1
        ttk.Label(f, foreground="#555", wraplength=420, justify="left",
                  text="Se guarda cifrada con tu usuario de Windows (no en texto plano) y solo sirve para copiarla "
                       "al portapapeles con el botón «Copiar contraseña»."
                  ).grid(row=fila, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.botones(f, "Guardar", self._ok).grid(row=fila + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        f.columnconfigure(1, weight=1)
        self.e_correo.focus_set()
        self.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        if "@" not in self.v_correo.get():
            messagebox.showwarning("Correo no válido", "Escribe un correo válido.", parent=self)
            return
        self.aceptar({"correo": self.v_correo.get().strip(), "clave": self.v_clave.get(),
                      "quitar_clave": self.v_quitar.get(), "grupo": self.v_grupo.get()})


class NuevoProyectoDialog(Dialogo):
    """Nombre, de qué se trata y correo del proyecto nuevo."""

    SIN = "(sin correo por ahora)"

    def __init__(self, master, srv, correo_pre=None):
        super().__init__(master, "Nuevo proyecto")
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        self.v_nombre, self.v_correo = tk.StringVar(), tk.StringVar()
        ttk.Label(f, text="Nombre del proyecto:").grid(row=0, column=0, sticky="w")
        self.e_nombre = ttk.Entry(f, textvariable=self.v_nombre, width=50)
        self.e_nombre.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=3)
        ttk.Label(f, text="Correo:").grid(row=1, column=0, sticky="w")
        self.etq = {self.SIN: None}
        ind = srv.indice()
        for gn, cuentas in ind["grupos"]:
            for c in cuentas:
                self.etq[etiqueta_correo(srv, gn, c, ind["por_correo"].get(c["correo"].lower(), []))] = c["correo"]
        pre = next((e for e, co in self.etq.items() if co and co == correo_pre), self.SIN)
        self.v_correo.set(pre)
        ttk.Combobox(f, textvariable=self.v_correo, values=list(self.etq), state="readonly", width=50).grid(
            row=1, column=1, sticky="ew", padx=(10, 0), pady=3)
        ttk.Label(f, text="De qué se trata:").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        self.t_desc = tk.Text(f, width=50, height=5, wrap="word", relief="flat", bd=0, highlightthickness=1, highlightbackground="#d1d1d6", highlightcolor="#0071e3", padx=8, pady=6)
        self.t_desc.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=(6, 3))
        ttk.Label(f, foreground="#555", wraplength=420, justify="left",
                  text="Un proyecto está en UN solo correo; un correo puede tener varios proyectos. "
                       "Puedes cambiarlo después desde la ficha del proyecto."
                  ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.botones(f, "Crear proyecto", self._ok).grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        f.columnconfigure(1, weight=1)
        self.e_nombre.focus_set()

    def _ok(self):
        if not self.v_nombre.get().strip():
            messagebox.showwarning("Falta el nombre", "Escribe el nombre del proyecto.", parent=self)
            return
        self.aceptar({"nombre": self.v_nombre.get().strip(), "descripcion": self.t_desc.get("1.0", "end").strip(),
                      "correo": self.etq.get(self.v_correo.get())})


class ConfigDialog(Dialogo):
    def __init__(self, master, cfg):
        super().__init__(master, "Configuración")
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        self.v_ruta = tk.StringVar(value=cfg["ruta_datos"])
        ttk.Label(f, text="Carpeta de datos (correos y proyectos):").grid(row=0, column=0, sticky="w")
        fr = ttk.Frame(f)
        fr.grid(row=1, column=0, sticky="ew")
        ttk.Entry(fr, textvariable=self.v_ruta, width=56).pack(side="left", fill="x", expand=True)
        ttk.Button(fr, text="Examinar…", command=self._examinar).pack(side="left", padx=(6, 0))
        ttk.Label(f, foreground="#555", wraplength=460, justify="left",
                  text="Para llevar tus datos a otro PC, copia o sincroniza esta carpeta y apunta la app a ella. "
                       "Las contraseñas guardadas solo se pueden leer con tu usuario de Windows en este PC."
                  ).grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.botones(f, "Guardar", self._ok).grid(row=3, column=0, sticky="e", pady=(12, 0))
        f.columnconfigure(0, weight=1)

    def _examinar(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.v_ruta.get() or None, title="Carpeta de datos")
        if d:
            self.v_ruta.set(d.replace("/", "\\") if "\\" in self.v_ruta.get() else d)

    def _ok(self):
        if not self.v_ruta.get().strip():
            messagebox.showwarning("Falta la carpeta", "Indica la carpeta de datos.", parent=self)
            return
        self.aceptar({"ruta_datos": self.v_ruta.get().strip()})


# ---------------------------------------------------------------------------
class GruposDialog(Dialogo):
    """Gestión de todos los correos: grupos, altas/bajas/ediciones, contraseñas en serie, cargar y exportar listas."""

    def __init__(self, master, srv):
        super().__init__(master, "Correos y contraseñas")
        self.srv = srv
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        ttk.Label(f, foreground="#555", wraplength=620, justify="left",
                  text="Aquí administras todos tus correos. La contraseña es opcional y se guarda cifrada con tu usuario "
                       "de Windows. 🔑 = tiene contraseña guardada."
                  ).pack(anchor="w", pady=(0, 6))
        cuerpo = ttk.Frame(f)
        cuerpo.pack(fill="both", expand=True)
        marco = ttk.Frame(cuerpo)
        marco.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(marco, show="tree", height=18, selectmode="browse")
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("grupo", font=("Segoe UI", 10, "bold"))
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        col = ttk.Frame(cuerpo, padding=(10, 0, 0, 0))
        col.pack(side="left", fill="y")
        for txt, cmd in [("➕ Nuevo grupo", self._nuevo_grupo), ("➕ Agregar correo", self._agregar_cuenta),
                         ("✏ Editar correo / contraseña", self._editar_cuenta),
                         ("↔ Pasar a otro grupo", self._mover),
                         ("🗑 Quitar seleccionado", self._quitar),
                         ("🔑 Poner contraseñas en serie", self._claves_en_serie),
                         ("📥 Cargar correos desde archivo", self._cargar_archivo),
                         ("📤 Exportar lista de correos", self._exportar_lista)]:
            ttk.Button(col, text=txt, command=cmd, width=30).pack(pady=3)
        ttk.Button(col, text="Cerrar", command=self.cancelar, width=30).pack(side="bottom", pady=3)
        self.refrescar()

    def refrescar(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        ind = self.srv.indice()
        for gn, cuentas in ind["grupos"]:
            self.tree.insert("", "end", f"g:{gn}", open=True, tags=("grupo",), text=f"{gn}  ({len(cuentas)} correos)")
            for c in cuentas:
                n = len(ind["por_correo"].get(c["correo"].lower(), []))
                self.tree.insert(f"g:{gn}", "end", f"c:{gn}|{c['correo']}",
                                 text=f"✉ {c['correo']}{' 🔑' if self.srv.tiene_clave(c) else ''}"
                                      + (f"   · {n} proyecto{'s' if n != 1 else ''}" if n else ""))
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showinfo("Selecciona algo", "Selecciona un grupo o un correo de la lista.", parent=self)
            return None
        return s[0]

    def _intentar(self, fn, *a):
        try:
            fn(*a)
        except ErrorRegla as e:
            messagebox.showwarning("No se puede", str(e), parent=self)
        self.refrescar()

    @staticmethod
    def _partir(s):
        """('g', grupo, None) o ('c', grupo, correo)."""
        if s.startswith("g:"):
            return "g", s[2:], None
        g, c = s[2:].split("|", 1)
        return "c", g, c

    def _nuevo_grupo(self):
        self._intentar(self.srv.crear_grupo)

    def _agregar_cuenta(self):
        grupos = self.srv.grupos()
        if not grupos:
            messagebox.showinfo("Falta un grupo", "Primero crea un grupo con «Nuevo grupo».", parent=self)
            return
        sel = self.tree.selection()
        d = CuentaDialog(self, "Agregar correo", grupos=grupos, grupo_pre=self._partir(sel[0])[1] if sel else None).mostrar()
        if d:
            self._intentar(self.srv.agregar_cuenta, d["grupo"], d["correo"], d["clave"] or None)
            iid = f"c:{d['grupo']}|{d['correo']}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _editar_cuenta(self):
        s = self._sel()
        if not s:
            return
        tipo, grupo, correo = self._partir(s)
        if tipo == "g":
            messagebox.showinfo("Selecciona un correo", "Para editar, selecciona un correo (no el grupo).", parent=self)
            return
        cuenta = next((c for c in self.srv.grupo(grupo)["cuentas"] if c["correo"] == correo), {})
        d = CuentaDialog(self, "Editar correo", correo, self.srv.tiene_clave(cuenta)).mostrar()
        if d:
            self._intentar(self.srv.editar_cuenta, grupo, correo, d["correo"], d["clave"] or None, d["quitar_clave"])

    def _mover(self):
        s = self._sel()
        if not s:
            return
        tipo, grupo, correo = self._partir(s)
        if tipo == "g":
            messagebox.showinfo("Selecciona un correo", "Selecciona el correo que quieres pasar a otro grupo.", parent=self)
            return
        otros = [(g, g) for g in self.srv.grupos() if g != grupo]
        if not otros:
            messagebox.showinfo("No hay otro grupo", "Crea otro grupo con «Nuevo grupo».", parent=self)
            return
        destino = ElegirDialog(self, "Pasar a otro grupo", f"{correo} está en {grupo}. ¿A qué grupo pasa?", otros).mostrar()
        if destino:
            self._intentar(self.srv.mover_cuenta, grupo, correo, destino)
            iid = f"c:{destino}|{correo}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _quitar(self):
        s = self._sel()
        if not s:
            return
        tipo, grupo, correo = self._partir(s)
        if tipo == "g":
            if messagebox.askyesno("Quitar grupo", f"¿Quitar «{grupo}»? (Solo se puede si está vacío.)", parent=self):
                self._intentar(self.srv.quitar_grupo, grupo)
        elif messagebox.askyesno("Quitar correo", f"¿Quitar {correo} de {grupo}?", parent=self):
            self._intentar(self.srv.quitar_cuenta, grupo, correo)

    def _claves_en_serie(self):
        """Recorre los correos SIN contraseña y pide una por una (vacío = saltar; Cancelar = terminar)."""
        pend = [(gn, c["correo"]) for gn, cuentas in self.srv.indice()["grupos"] for c in cuentas
                if not self.srv.tiene_clave(c)]
        if not pend:
            messagebox.showinfo("Todo listo", "Todos los correos ya tienen contraseña guardada.", parent=self)
            return
        guardadas = 0
        for i, (gn, correo) in enumerate(pend, 1):
            clave = simpledialog.askstring(
                f"Contraseña {i} de {len(pend)}",
                f"{correo}\n({gn})\n\nContraseña (vacío = saltar este correo; Cancelar = terminar):",
                show="•", parent=self)
            if clave is None:
                break
            if clave:
                try:
                    self.srv.editar_cuenta(gn, correo, clave=clave)
                    guardadas += 1
                except ErrorRegla as e:
                    messagebox.showwarning("No se pudo guardar", str(e), parent=self)
                    break
        self.refrescar()
        messagebox.showinfo("Contraseñas", f"Se guardaron {guardadas} contraseña(s). Puedes repetir esto para las que falten.", parent=self)

    def _cargar_archivo(self):
        ruta = filedialog.askopenfilename(parent=self, title="Archivo de correos (.json)",
                                          filetypes=[("Correos (JSON)", "*.json"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            grupos = cuentas_lote.leer_archivo(ruta)
            resumen = "\n".join(f"• {g}: {len(c)} correo(s)" for g, c in grupos.items())
            r = cuentas_lote.cargar(self.srv, grupos, lambda quitar: messagebox.askyesno(
                "Cargar correos", f"Se crearán o actualizarán estos grupos:\n{resumen}\n\n"
                + ("Se quitarán los grupos con nombre anterior: " + ", ".join(quitar) + "\n\n" if quitar else "")
                + "Los correos de ejemplo se reemplazan y las contraseñas y proyectos ya guardados se conservan.\n\n¿Continuar?",
                parent=self))
        except ErrorRegla as e:
            messagebox.showwarning("No se pudo cargar", str(e), parent=self)
            return
        self.refrescar()
        if r:
            messagebox.showinfo("Correos cargados", f"{r[1]} correo(s) nuevo(s).\nAhora usa «🔑 Poner contraseñas en serie».", parent=self)

    def _exportar_lista(self):
        ruta = filedialog.asksaveasfilename(parent=self, defaultextension=".json", initialfile="mis_cuentas.json",
                                            filetypes=[("Correos (JSON)", "*.json")], title="Guardar lista de correos")
        if not ruta:
            return
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(cuentas_lote.exportar(self.srv), f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Lista exportada", "Se guardó la lista de grupos y correos (sin contraseñas ni proyectos).\n"
                            "En otro PC usa «📥 Cargar correos desde archivo».", parent=self)
