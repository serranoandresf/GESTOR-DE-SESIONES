"""Ventana principal: lista de correos y proyectos (izquierda) + ficha de lo que selecciones (derecha)."""
import sys
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from . import __version__
from . import cuentas_lote
from .almacen import Almacen
from .config import Config
from .dialogos import ConfigDialog, CuentaDialog, GruposDialog, NuevoProyectoDialog, etiqueta_correo
from .ejemplo import crear_datos_ejemplo
from .reglas import ESTADOS, ICONO_ESTADO, ErrorRegla, Servicio

SIN_CORREO = "(sin correo)"
TODOS = "Todos los estados"
COLOR_GRIS = "#636366"
COLOR_AVISO = "#9a4a08"
PAPEL, SUPERFICIE, SUPERFICIE_2, SUPERFICIE_3 = "#f2f2f7", "#ffffff", "#f2f2f7", "#e5e5ea"
TINTA, BORDE, ACENTO = "#1c1c1e", "#d1d1d6", "#0071e3"


def seguro(fn):
    """Muestra los errores de regla como avisos amables en vez de cerrar el programa."""
    def envoltura(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except ErrorRegla as e:
            messagebox.showwarning("No se puede hacer", str(e), parent=self)
        except OSError as e:
            messagebox.showerror("Error de archivo", f"No se pudo leer o escribir un archivo:\n{e}", parent=self)
    envoltura.__name__ = fn.__name__
    return envoltura


def _texto_con_scroll(padre, alto):
    marco = ttk.Frame(padre)
    t = tk.Text(marco, height=alto, wrap="word", relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDE, highlightcolor=ACENTO, bg=SUPERFICIE, fg=TINTA, insertbackground=TINTA, padx=8, pady=6, undo=True, font="TkDefaultFont")
    sb = ttk.Scrollbar(marco, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")
    return marco, t


class App(tk.Tk):
    def __init__(self, config=None):
        super().__init__()
        self.title(f"Gestor de Sesiones  ·  correos y proyectos  ·  v{__version__}")
        self._poner_icono()
        ancho = min(1200, self.winfo_screenwidth() - 60)
        alto = min(760, self.winfo_screenheight() - 100)
        self.geometry(f"{ancho}x{alto}")
        self.minsize(min(980, ancho), min(560, alto))
        self.cfg = config or Config()
        self.sel = None                 # iid seleccionado en la lista
        self.proy_actual = None         # proyecto cargado en la ficha
        self.ind = {"grupos": [], "proyectos": {}, "por_correo": {}, "sin_correo": []}
        self._cargando = False
        self._sucio = False
        self._abrir_servicio()
        self._estilo()
        self._construir()
        self.report_callback_exception = self._excepcion
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind_all("<Control-s>", lambda e: self.accion_guardar())
        self.bind_all("<Control-f>", lambda e: (self.e_buscar.focus_set(), self.e_buscar.select_range(0, "end")))
        self.refrescar_todo()
        self.after(300, self._arranque)

    def _poner_icono(self):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "gestor_sesiones" / "recursos"
        try:
            if sys.platform == "win32":
                self.iconbitmap(default=str(base / "icono.ico"))
            else:
                self._icono = tk.PhotoImage(file=str(base / "icono.png"))
                self.iconphoto(True, self._icono)
        except Exception:
            pass      # sin icono la app funciona igual

    # ------------------------------------------------------------- arranque
    def _abrir_servicio(self):
        self.srv = Servicio(Almacen(self.cfg["ruta_datos"]), self.cfg)

    def _arranque(self):
        if not self.srv.hay_datos():
            lista = Path(__file__).resolve().parent.parent / "mis_cuentas.json"
            try:
                if lista.exists() and messagebox.askyesno(
                        "Primer uso", "No hay correos ni proyectos todavía.\n\nEncontré tu lista de correos "
                        "(mis_cuentas.json). ¿Cargarla ahora?", parent=self):
                    cuentas_lote.cargar(self.srv, cuentas_lote.leer_archivo(lista))
                elif messagebox.askyesno("Primer uso", "¿Crear datos de ejemplo (2 grupos y 3 proyectos) para practicar?\n"
                                         "Los puedes borrar o reemplazar cuando quieras.", parent=self):
                    crear_datos_ejemplo(self.srv)
            except (ErrorRegla, OSError) as e:
                messagebox.showwarning("Primer uso", str(e), parent=self)
            self.refrescar_todo()
        avisos = self.srv.verificar_reglas()
        if avisos:
            messagebox.showwarning("Revisión de datos", "Se encontraron inconsistencias:\n\n• " + "\n• ".join(avisos), parent=self)

    def _excepcion(self, exc, val, tb):
        messagebox.showerror("Error inesperado", f"{exc.__name__}: {val}\n\nTus datos no se modificaron a medias: "
                             "las escrituras son atómicas. Puedes seguir usando la app.", parent=self)

    def _estilo(self):
        """Aspecto sobrio: papel frío, superficies planas y un solo color de acento (mismo sistema que la versión móvil)."""
        fam = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
        for nombre in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            tkfont.nametofont(nombre).configure(family=fam, size=10)
        st = ttk.Style(self)
        st.theme_use("clam")                      # el único tema que respeta bien los colores en todos los sistemas
        self.configure(bg=PAPEL)
        st.configure(".", background=PAPEL, foreground=TINTA, bordercolor=BORDE, lightcolor=PAPEL, darkcolor=PAPEL,
                     troughcolor=SUPERFICIE_2, focuscolor=ACENTO, selectbackground=ACENTO, selectforeground="#ffffff")
        st.configure("TFrame", background=PAPEL)
        st.configure("TLabel", background=PAPEL, foreground=TINTA)
        st.configure("TLabelframe", background=PAPEL, bordercolor=BORDE)
        st.configure("TLabelframe.Label", background=PAPEL, foreground=COLOR_GRIS, font=(fam, 9, "bold"))
        st.configure("TButton", background=SUPERFICIE, foreground=TINTA, bordercolor=BORDE, padding=(12, 6), relief="flat")
        st.map("TButton", background=[("pressed", SUPERFICIE_3), ("active", SUPERFICIE_2)], bordercolor=[("focus", ACENTO)])
        st.configure("Accent.TButton", background=ACENTO, foreground="#ffffff", bordercolor=ACENTO, padding=(14, 6),
                     font=(fam, 10, "bold"))
        st.map("Accent.TButton", background=[("disabled", "#a9cdf3"), ("pressed", "#005bb8"), ("active", "#0a64c8")],
               foreground=[("disabled", "#ffffff")], bordercolor=[("disabled", "#a9cdf3")])
        st.map("TButton", foreground=[("disabled", "#a1a1a6")])
        for w in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(w, fieldbackground=SUPERFICIE, background=SUPERFICIE, foreground=TINTA, bordercolor=BORDE, padding=5)
            st.map(w, bordercolor=[("focus", ACENTO)], fieldbackground=[("readonly", SUPERFICIE), ("disabled", SUPERFICIE_2)],
                   foreground=[("disabled", COLOR_GRIS)], selectbackground=[("readonly", SUPERFICIE)],
                   selectforeground=[("readonly", TINTA)])
        st.configure("TCheckbutton", background=PAPEL)
        st.configure("Estado.Toolbutton", background=SUPERFICIE, foreground=TINTA, bordercolor=BORDE, padding=(10, 5),
                     relief="flat", anchor="center")
        st.map("Estado.Toolbutton", background=[("selected", TINTA), ("active", SUPERFICIE_2)],
               foreground=[("selected", "#ffffff")], bordercolor=[("selected", TINTA)])
        st.configure("TPanedwindow", background=BORDE)
        st.configure("Sash", sashthickness=1, background=BORDE)
        st.configure("TScrollbar", background=SUPERFICIE_3, troughcolor=PAPEL, bordercolor=PAPEL, arrowcolor=COLOR_GRIS)
        st.configure("Treeview", background=SUPERFICIE, fieldbackground=SUPERFICIE, foreground=TINTA, bordercolor=BORDE,
                     rowheight=30, borderwidth=0, relief="flat")
        st.configure("Treeview.Heading", font=(fam, 10, "bold"), background=SUPERFICIE_2, foreground=COLOR_GRIS)
        st.map("Treeview", background=[("selected", ACENTO)], foreground=[("selected", "#ffffff")])
        self.option_add("*TCombobox*Listbox.background", SUPERFICIE)
        self.option_add("*TCombobox*Listbox.selectBackground", ACENTO)

    # ----------------------------------------------------------- construcción
    def _construir(self):
        barra = ttk.Frame(self, padding=(8, 8, 8, 4))
        barra.pack(fill="x")
        for txt, cmd in [("➕ Nuevo proyecto", self.accion_nuevo_proyecto), ("✉ Nuevo correo", self.accion_nuevo_correo),
                         ("👥 Gestionar correos", self.accion_grupos), ("📤 Exportar lista (Excel)", self.accion_exportar_csv),
                         ("📥 Importar lista", self.accion_importar_csv),
                         ("⚙ Configuración", self.accion_config), ("🔍 Revisar datos", self.accion_revisar)]:
            ttk.Button(barra, text=txt, command=cmd).pack(side="left", padx=(0, 6))
        self.l_msg = ttk.Label(self, anchor="w", padding=(10, 4), relief="sunken")
        self.l_msg.pack(fill="x", side="bottom")
        cuerpo = ttk.PanedWindow(self, orient="horizontal")
        cuerpo.pack(fill="both", expand=True)
        izq, centro = ttk.Frame(cuerpo, padding=8), ttk.Frame(cuerpo, padding=(12, 8))
        cuerpo.add(izq, weight=0)
        cuerpo.add(centro, weight=1)
        self._panel_izq(izq)
        self.centro = centro
        self.f_vacio = self._vista_vacia(centro)
        self.f_proyecto = self._vista_proyecto(centro)
        self.f_correo = self._vista_correo(centro)
        self.f_grupo = self._vista_grupo(centro)

    def _panel_izq(self, f):
        f.config(width=380)
        ttk.Label(f, text="Correos y proyectos", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.l_resumen = ttk.Label(f, foreground=COLOR_GRIS, wraplength=360, justify="left")
        self.l_resumen.pack(anchor="w", pady=(2, 0))
        self.v_buscar = tk.StringVar()
        fila = ttk.Frame(f)
        fila.pack(fill="x", pady=(6, 6))
        ttk.Label(fila, text="🔍").pack(side="left", padx=(0, 4))
        self.e_buscar = ttk.Entry(fila, textvariable=self.v_buscar)
        self.e_buscar.pack(side="left", fill="x", expand=True)
        ttk.Button(fila, text="✕", width=3, command=lambda: self.v_buscar.set("")).pack(side="left", padx=(4, 0))
        self.v_buscar.trace_add("write", lambda *a: self._refrescar_arbol())
        fe = ttk.Frame(f)
        fe.pack(fill="x", pady=(0, 6))
        ttk.Label(fe, text="Mostrar:").pack(side="left", padx=(0, 6))
        self.v_filtro = tk.StringVar(value=TODOS)
        cb = ttk.Combobox(fe, textvariable=self.v_filtro, values=[TODOS] + ESTADOS, state="readonly", width=22)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._refrescar_arbol())
        marco = ttk.Frame(f)
        marco.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(marco, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("grupo", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("libre", foreground=COLOR_GRIS)
        self.tree.tag_configure("sin_correo", foreground=COLOR_AVISO)
        self.tree.tag_configure("completado", foreground=COLOR_GRIS)
        self.tree.tag_configure("pausado", foreground=COLOR_AVISO)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)
        ttk.Label(f, foreground="#666", wraplength=350, justify="left",
                  text="✉ correo (n = proyectos; en gris, sin proyectos)  ·  ○ por empezar  ● en curso  ⏸ pausado  ✔ completado"
                  ).pack(anchor="w", pady=(6, 0))

    def _vista_vacia(self, padre):
        f = ttk.Frame(padre)
        self.l_vacio = ttk.Label(f, font=("Segoe UI", 12), foreground="#444", wraplength=560, justify="left")
        self.l_vacio.pack(anchor="nw", pady=20)
        return f

    def _vista_proyecto(self, padre):
        f = ttk.Frame(padre)
        self.l_tit_p = ttk.Label(f, font=("Segoe UI", 17, "bold"))
        self.l_tit_p.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.v_nombre = tk.StringVar()
        self.v_correo_p = tk.StringVar()
        ttk.Label(f, text="Nombre").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.v_nombre).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(f, text="Correo").grid(row=2, column=0, sticky="w", pady=4)
        self.c_correo = ttk.Combobox(f, textvariable=self.v_correo_p, state="readonly")
        self.c_correo.grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=4)
        self.l_aviso_p = ttk.Label(f, foreground=COLOR_AVISO, wraplength=520, justify="left")
        self.l_aviso_p.grid(row=3, column=1, sticky="w", padx=(12, 0))
        ttk.Label(f, text="Estado").grid(row=4, column=0, sticky="w", pady=(10, 4))
        self.v_estado = tk.StringVar(value=ESTADOS[1])
        fe = ttk.Frame(f)
        fe.grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(10, 4))
        for e in ESTADOS:
            ttk.Radiobutton(fe, text=f"{ICONO_ESTADO[e]} {e}", value=e, variable=self.v_estado,
                            style="Estado.Toolbutton").pack(side="left", padx=(0, 4))
        ttk.Label(f, text="Próximo paso").grid(row=5, column=0, sticky="w", pady=4)
        self.v_paso = tk.StringVar()
        ttk.Entry(f, textvariable=self.v_paso).grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(f, text="De qué se trata").grid(row=6, column=0, sticky="nw", pady=(10, 4))
        m1, self.t_desc = _texto_con_scroll(f, 5)
        m1.grid(row=6, column=1, sticky="nsew", padx=(12, 0), pady=(10, 4))
        ttk.Label(f, text="Notas").grid(row=7, column=0, sticky="nw", pady=(6, 4))
        m2, self.t_notas = _texto_con_scroll(f, 7)
        m2.grid(row=7, column=1, sticky="nsew", padx=(12, 0), pady=(6, 4))
        self.l_act = ttk.Label(f, foreground=COLOR_GRIS)
        self.l_act.grid(row=8, column=1, sticky="w", padx=(12, 0))
        fila = ttk.Frame(f)
        fila.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.b_guardar = ttk.Button(fila, text="Guardar cambios  (Ctrl+S)", command=self.accion_guardar, style="Accent.TButton")
        self.b_guardar.pack(side="left")
        self.b_descartar = ttk.Button(fila, text="↺ Descartar", command=self.accion_descartar)
        self.b_descartar.pack(side="left", padx=6)
        self.l_sucio = ttk.Label(fila, foreground=COLOR_AVISO)
        self.l_sucio.pack(side="left", padx=8)
        ttk.Button(fila, text="🗑 Eliminar proyecto", command=self.accion_eliminar_proyecto).pack(side="right")
        self.b_completar = ttk.Button(fila, text="✔ Marcar completado", command=self.accion_alternar_completado)
        self.b_completar.pack(side="right", padx=6)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(6, weight=1)
        f.rowconfigure(7, weight=2)
        for var in (self.v_nombre, self.v_correo_p, self.v_estado, self.v_paso):
            var.trace_add("write", lambda *a: self._cambio_en_ficha())
        for t in (self.t_desc, self.t_notas):
            t.bind("<<Modified>>", self._texto_modificado)
        return f

    def _tabla(self, padre, columnas, anchos, alto=12):
        marco = ttk.Frame(padre)
        t = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=alto, selectmode="browse")
        for (cid, titulo), ancho in zip(columnas, anchos):
            t.heading(cid, text=titulo)
            t.column(cid, width=ancho, anchor="w")
        sb = ttk.Scrollbar(marco, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        return marco, t

    def _vista_correo(self, padre):
        f = ttk.Frame(padre)
        self.l_tit_c = ttk.Label(f, font=("Segoe UI", 16, "bold"))
        self.l_tit_c.pack(anchor="w")
        self.l_sub_c = ttk.Label(f, foreground="#555")
        self.l_sub_c.pack(anchor="w", pady=(0, 10))
        ttk.Label(f, text="Proyectos de este correo (haz clic en uno para abrirlo):").pack(anchor="w")
        m, self.t_proy_c = self._tabla(f, [("proyecto", "Proyecto"), ("estado", "Estado"), ("desc", "De qué se trata / próximo paso")], [190, 110, 340])
        m.pack(fill="both", expand=True, pady=(4, 8))
        self.t_proy_c.bind("<<TreeviewSelect>>", lambda e: self._abrir_desde_tabla(self.t_proy_c, "p:"))
        fila = ttk.Frame(f)
        fila.pack(fill="x")
        ttk.Button(fila, text="➕ Proyecto nuevo en este correo", command=self.accion_proyecto_en_correo).pack(side="left")
        ttk.Button(fila, text="✉ Copiar correo", command=self.accion_copiar_correo).pack(side="left", padx=6)
        self.b_copiar_clave = ttk.Button(fila, text="🔑 Copiar contraseña (se borra a los 30 s)", command=self.accion_copiar_clave)
        self.b_copiar_clave.pack(side="left")
        fila2 = ttk.Frame(f)
        fila2.pack(fill="x", pady=(8, 0))
        ttk.Button(fila2, text="✏ Editar correo / contraseña", command=self.accion_editar_correo).pack(side="left")
        ttk.Button(fila2, text="🗑 Quitar correo", command=self.accion_quitar_correo).pack(side="right")
        return f

    def _vista_grupo(self, padre):
        f = ttk.Frame(padre)
        self.l_tit_g = ttk.Label(f, font=("Segoe UI", 16, "bold"))
        self.l_tit_g.pack(anchor="w")
        self.l_sub_g = ttk.Label(f, foreground="#555")
        self.l_sub_g.pack(anchor="w", pady=(0, 10))
        m, self.t_cor_g = self._tabla(f, [("correo", "Correo"), ("n", "Proyectos"), ("act", "En curso"), ("clave", "Contraseña")], [310, 80, 80, 110])
        m.pack(fill="both", expand=True, pady=(0, 8))
        self.t_cor_g.bind("<<TreeviewSelect>>", lambda e: self._abrir_desde_tabla(self.t_cor_g, "c:"))
        ttk.Button(f, text="➕ Correo nuevo en este grupo", command=self.accion_correo_en_grupo).pack(anchor="w")
        return f

    # ----------------------------------------------------------- utilidades
    def msg(self, texto):
        self.l_msg.config(text=texto)

    def _mostrar(self, vista):
        for v in (self.f_vacio, self.f_proyecto, self.f_correo, self.f_grupo):
            v.pack_forget()
        vista.pack(fill="both", expand=True)

    def _cuenta(self, grupo, correo):
        for gn, cuentas in self.ind["grupos"]:
            if gn == grupo:
                return next((c for c in cuentas if c["correo"] == correo), None)
        return None

    @staticmethod
    def _partir_c(iid):
        g, c = iid[2:].split("|", 1)
        return g, c

    def _puedo_continuar(self):
        """True si no hay cambios sin guardar (o si el usuario decide guardarlos/descartarlos)."""
        return (not self._sucio) or self._resolver_sucio()

    def _resolver_sucio(self):
        r = messagebox.askyesnocancel("Cambios sin guardar", f"Hay cambios sin guardar en «{self.proy_actual}».\n\n"
                                      "¿Quieres guardarlos?", parent=self)
        if r is None:
            return False
        if r:
            return self._guardar_proyecto()
        self._set_sucio(False)
        return True

    def _cerrar(self):
        if self._puedo_continuar():
            self.destroy()

    # ------------------------------------------------------------ la lista
    def refrescar_todo(self):
        self._refrescar_arbol()
        if not self._sucio:
            self._mostrar_seleccion()

    def _refrescar_arbol(self):
        ind = self.ind = self.srv.indice()
        f = self.v_buscar.get().strip().lower()
        self.tree.delete(*self.tree.get_children())

        filtro = self.v_filtro.get()
        r = self.srv.resumen()
        pe = r["por_estado"]
        self.l_resumen.config(text=f"{r['correos']} correos · {r['proyectos']} proyectos\n"
                                   f"● {pe['En curso']} en curso   ○ {pe['Por empezar']} por empezar   "
                                   f"⏸ {pe['Pausado']} pausados   ✔ {pe['Completado']} completados")

        def estado_ok(pn):
            return filtro == TODOS or ind["proyectos"][pn]["estado"] == filtro

        def coincide(pn):
            p = ind["proyectos"][pn]
            return f in f"{pn} {p['descripcion']} {p['notas']} {p['proximo_paso']}".lower()

        def etiqueta(pn):
            e = ind["proyectos"][pn]["estado"]
            return f"{ICONO_ESTADO[e]} {pn}", {"Completado": ("completado",), "Pausado": ("pausado",)}.get(e, ())

        for gn, cuentas in ind["grupos"]:
            hijos = []
            for c in cuentas:
                nombres = ind["por_correo"].get(c["correo"].lower(), [])
                c_ok = (not f) or f in c["correo"].lower() or f in gn.lower()
                vis = [pn for pn in (nombres if c_ok else [pn for pn in nombres if coincide(pn)]) if estado_ok(pn)]
                if (c_ok and filtro == TODOS) or vis:
                    hijos.append((c, nombres, vis))
            if (f or filtro != TODOS) and not hijos:
                continue
            gid = f"g:{gn}"
            self.tree.insert("", "end", gid, open=True, tags=("grupo",), text=f"{gn}  ({len(cuentas)} correos)")
            for c, nombres, vis in hijos:
                cid = f"c:{gn}|{c['correo']}"
                self.tree.insert(gid, "end", cid, open=bool(vis), tags=() if nombres else ("libre",),
                                 text=f"✉ {c['correo']}" + (f"   ({len(nombres)})" if nombres else ""))
                for pn in vis:
                    txt, tg = etiqueta(pn)
                    self.tree.insert(cid, "end", f"p:{pn}", tags=tg, text=txt)
        sueltos = [pn for pn in ind["sin_correo"] if ((not f) or coincide(pn)) and estado_ok(pn)]
        if sueltos:
            self.tree.insert("", "end", "raiz_s", open=True, tags=("grupo", "sin_correo"), text="📂 SIN CORREO ASIGNADO")
            for pn in sueltos:
                self.tree.insert("raiz_s", "end", f"p:{pn}", tags=("sin_correo",), text=etiqueta(pn)[0])
        if self.sel and self.tree.exists(self.sel):
            self.tree.selection_set(self.sel)
            self.tree.see(self.sel)
        elif not self._sucio:
            self.sel = None
        if f:
            self.msg(f"🔍 Mostrando lo que coincide con «{self.v_buscar.get().strip()}».")
        elif filtro != TODOS:
            self.msg(f"Mostrando solo proyectos «{filtro}».")

    def _al_seleccionar(self, _e=None):
        s = self.tree.selection()
        nuevo = s[0] if s else None
        if nuevo == self.sel or nuevo is None:
            return
        if self._sucio and not self._resolver_sucio():
            if self.sel and self.tree.exists(self.sel):
                self.tree.selection_set(self.sel)            # vuelve a lo que estaba editando
            return
        self.sel = nuevo
        if self.tree.exists(nuevo) and self.tree.selection() != (nuevo,):
            self.tree.selection_set(nuevo)                   # guardar pudo repintar la lista: vuelve a lo que pidió el usuario
        self._mostrar_seleccion()

    def _abrir_desde_tabla(self, tabla, prefijo):
        """Clic en una fila de las tablas de la ficha: abre ese proyecto/correo en la lista."""
        if self._cargando:
            return
        s = tabla.selection()
        if not s:
            return
        iid = s[0]
        if not self.tree.exists(iid):
            self.v_buscar.set("")                           # el filtro lo ocultaba
            self.update_idletasks()
        if self.tree.exists(iid):
            self.tree.selection_set(iid)

    def _mostrar_seleccion(self):
        iid = self.sel
        self._cargando = True
        try:
            if iid and iid.startswith("p:") and iid[2:] in self.ind["proyectos"]:
                self._cargar_proyecto(iid[2:])
            elif iid and iid.startswith("c:") and self._cuenta(*self._partir_c(iid)):
                self._cargar_correo(*self._partir_c(iid))
            elif iid and iid.startswith("g:") and any(g == iid[2:] for g, _ in self.ind["grupos"]):
                self._cargar_grupo(iid[2:])
            else:
                self._cargar_vacio()
        finally:
            self._cargando = False
        self._set_sucio(False)

    # -------------------------------------------------------------- vistas
    def _cargar_vacio(self):
        if not self.ind["grupos"] and not self.ind["proyectos"]:
            self.l_vacio.config(text="Aún no hay correos ni proyectos.\n\n• «✉ Nuevo correo» agrega un correo.\n"
                                     "• «👥 Gestionar correos» → «📥 Cargar correos desde archivo» carga varios de una vez.\n"
                                     "• «➕ Nuevo proyecto» crea un proyecto y lo asigna a un correo.")
        else:
            self.l_vacio.config(text="👈 Elige un correo o un proyecto de la lista.\n\n"
                                     "Cada proyecto está en UN solo correo; un correo puede tener varios proyectos.\n"
                                     "Usa el 🔍 de arriba para buscar por correo, nombre o descripción.")
        self._mostrar(self.f_vacio)

    def _opciones_correo(self):
        """[(etiqueta, correo|None)] para elegir el correo de un proyecto."""
        ops = [(SIN_CORREO, None)]
        for gn, cuentas in self.ind["grupos"]:
            for c in cuentas:
                ops.append((etiqueta_correo(self.srv, gn, c, self.ind["por_correo"].get(c["correo"].lower(), [])), c["correo"]))
        return ops

    def _poner_texto(self, t, texto):
        t.delete("1.0", "end")
        t.insert("1.0", texto or "")
        t.edit_modified(False)
        t.edit_reset()

    def _cargar_proyecto(self, nombre):
        p = self.ind["proyectos"][nombre]
        self.proy_actual = nombre
        self.l_tit_p.config(text=f"{ICONO_ESTADO[p['estado']]} {nombre}")
        self.v_nombre.set(nombre)
        ops = self._opciones_correo()
        self.etq_correo = dict(ops)
        self.c_correo.config(values=[e for e, _ in ops])
        actual = (p.get("correo") or "")
        marca = next((e for e, co in ops if co and co.lower() == actual.lower()), SIN_CORREO)
        self.v_correo_p.set(marca)
        self.l_aviso_p.config(text=(f"Su correo anterior ({actual}) ya no está registrado. Elige otro."
                                    if actual and marca == SIN_CORREO else ""))
        self.v_estado.set(p["estado"])
        self.v_paso.set(p.get("proximo_paso", ""))
        self.l_act.config(text=f"Última actualización: {p['actualizado']}" if p.get("actualizado") else "")
        self.b_completar.config(text="↺ Reabrir (En curso)" if p["estado"] == "Completado" else "✔ Marcar completado")
        self._poner_texto(self.t_desc, p.get("descripcion"))
        self._poner_texto(self.t_notas, p.get("notas"))
        self._mostrar(self.f_proyecto)
        self.msg(f"📁 {nombre}")

    def _cargar_correo(self, grupo, correo):
        c = self._cuenta(grupo, correo)
        nombres = self.ind["por_correo"].get(correo.lower(), [])
        self.l_tit_c.config(text=f"✉ {correo}")
        clave = "🔑 con contraseña guardada" if self.srv.tiene_clave(c) else "sin contraseña guardada"
        self.l_sub_c.config(text=f"{grupo}  ·  {len(nombres)} proyecto{'s' if len(nombres) != 1 else ''}  ·  {clave}")
        self.t_proy_c.delete(*self.t_proy_c.get_children())
        for pn in nombres:
            pr = self.ind["proyectos"][pn]
            d = (pr["descripcion"] + (f"  →  {pr['proximo_paso']}" if pr["proximo_paso"] else "")).replace("\n", " ")
            self.t_proy_c.insert("", "end", f"p:{pn}", values=(pn, f"{ICONO_ESTADO[pr['estado']]} {pr['estado']}",
                                                               d[:110] + ("…" if len(d) > 110 else "")))
        self.b_copiar_clave.config(state="normal" if self.srv.tiene_clave(c) else "disabled")
        self._mostrar(self.f_correo)
        self.msg(f"✉ {correo}")

    def _cargar_grupo(self, grupo):
        cuentas = next(c for g, c in self.ind["grupos"] if g == grupo)
        self.l_tit_g.config(text=grupo)
        self.l_sub_g.config(text=f"{len(cuentas)} correo{'s' if len(cuentas) != 1 else ''}  ·  haz clic en uno para abrirlo")
        self.t_cor_g.delete(*self.t_cor_g.get_children())
        for c in cuentas:
            nombres = self.ind["por_correo"].get(c["correo"].lower(), [])
            act = sum(1 for pn in nombres if self.ind["proyectos"][pn]["estado"] == "En curso")
            self.t_cor_g.insert("", "end", f"c:{grupo}|{c['correo']}",
                                values=(c["correo"], len(nombres), act, "🔑 sí" if self.srv.tiene_clave(c) else "—"))
        self._mostrar(self.f_grupo)
        self.msg(grupo)

    # ------------------------------------------------- ficha del proyecto
    def _set_sucio(self, valor):
        self._sucio = valor
        self.l_sucio.config(text="● Cambios sin guardar" if valor else "")
        estado = "normal" if valor else "disabled"
        self.b_guardar.config(state=estado)
        self.b_descartar.config(state=estado)

    def _cambio_en_ficha(self):
        if not self._cargando:
            self._set_sucio(True)

    def _texto_modificado(self, e):
        w = e.widget
        if w.edit_modified():
            w.edit_modified(False)
            if not self._cargando:
                self._set_sucio(True)

    def _guardar_proyecto(self):
        """Guarda la ficha. Devuelve True si quedó guardada."""
        if not self.proy_actual:
            return True
        nuevo = self.v_nombre.get().strip()
        try:
            self.srv.actualizar_proyecto(
                self.proy_actual, nuevo_nombre=nuevo, descripcion=self.t_desc.get("1.0", "end"),
                notas=self.t_notas.get("1.0", "end"), correo=self.etq_correo.get(self.v_correo_p.get()),
                estado=self.v_estado.get(), proximo_paso=self.v_paso.get())
        except ErrorRegla as e:
            messagebox.showwarning("No se pudo guardar", str(e), parent=self)
            return False
        except OSError as e:
            messagebox.showerror("Error de archivo", f"No se pudo guardar:\n{e}", parent=self)
            return False
        self._set_sucio(False)
        self.sel = f"p:{nuevo}"
        self.refrescar_todo()
        self.msg(f"✅ «{nuevo}» guardado.")
        return True

    @seguro
    def accion_guardar(self):
        if self._sucio:
            self._guardar_proyecto()

    @seguro
    def accion_alternar_completado(self):
        """Atajo: completado ↔ en curso, y guarda la ficha en el momento."""
        if not self.proy_actual:
            return
        self.v_estado.set("En curso" if self.v_estado.get() == "Completado" else "Completado")
        self._guardar_proyecto()

    @seguro
    def accion_descartar(self):
        if self._sucio and self.proy_actual:
            self._set_sucio(False)
            self._mostrar_seleccion()
            self.msg("Cambios descartados.")

    @seguro
    def accion_eliminar_proyecto(self):
        nombre = self.proy_actual
        if not nombre:
            return
        if not messagebox.askyesno("Eliminar proyecto", f"¿Eliminar «{nombre}»?\n\nSe guarda una copia en la carpeta "
                                   "«respaldos» dentro de tu carpeta de datos.", parent=self):
            return
        self.srv.quitar_proyecto(nombre)
        self._set_sucio(False)
        self.sel = None
        self.refrescar_todo()
        self.msg(f"«{nombre}» eliminado (copia en respaldos).")

    # ----------------------------------------- acciones de la ficha de correo
    def _correo_sel(self):
        if self.sel and self.sel.startswith("c:"):
            return self._partir_c(self.sel)
        return None

    @seguro
    def accion_proyecto_en_correo(self):
        c = self._correo_sel()
        self.accion_nuevo_proyecto(correo_pre=c[1] if c else None)

    @seguro
    def accion_copiar_correo(self):
        c = self._correo_sel()
        if not c:
            return
        self.clipboard_clear()
        self.clipboard_append(c[1])
        self.update()
        self.msg(f"✅ Correo copiado: {c[1]}. Pégalo con Ctrl+V.")

    @seguro
    def accion_copiar_clave(self):
        c = self._correo_sel()
        if not c:
            return
        clave = self.srv.obtener_clave(*c)
        if not clave:
            raise ErrorRegla(f"{c[1]} no tiene contraseña guardada.\nAgrégala con «✏ Editar correo / contraseña».")
        self.clipboard_clear()
        self.clipboard_append(clave)
        self.update()
        self.msg("✅ Contraseña copiada. Pégala con Ctrl+V; se borra del portapapeles en 30 segundos.")
        self.after(30000, lambda: self._borrar_portapapeles_si(clave))

    def _borrar_portapapeles_si(self, valor):
        try:
            if self.clipboard_get() == valor:
                self.clipboard_clear()
                self.clipboard_append("")
                self.msg("🧹 Contraseña borrada del portapapeles.")
        except tk.TclError:
            pass

    @seguro
    def accion_editar_correo(self):
        c = self._correo_sel()
        if not c or not self._puedo_continuar():
            return
        grupo, correo = c
        d = CuentaDialog(self, "Editar correo", correo, self.srv.tiene_clave(self._cuenta(grupo, correo) or {})).mostrar()
        if not d:
            return
        self.srv.editar_cuenta(grupo, correo, d["correo"], d["clave"] or None, d["quitar_clave"])
        self.sel = f"c:{grupo}|{d['correo']}"
        self.refrescar_todo()
        self.msg("✅ Correo actualizado.")

    @seguro
    def accion_quitar_correo(self):
        c = self._correo_sel()
        if not c or not self._puedo_continuar():
            return
        if not messagebox.askyesno("Quitar correo", f"¿Quitar {c[1]} de {c[0]}?", parent=self):
            return
        self.srv.quitar_cuenta(*c)
        self.sel = f"g:{c[0]}"
        self.refrescar_todo()
        self.msg(f"{c[1]} quitado.")

    @seguro
    def accion_correo_en_grupo(self):
        self.accion_nuevo_correo()

    # ------------------------------------------------------ barra superior
    @seguro
    def accion_nuevo_proyecto(self, correo_pre=None):
        if not self._puedo_continuar():
            return
        if correo_pre is None:
            if self.sel and self.sel.startswith("c:"):
                correo_pre = self._partir_c(self.sel)[1]
            elif self.sel and self.sel.startswith("p:"):
                correo_pre = (self.ind["proyectos"].get(self.sel[2:]) or {}).get("correo")
        d = NuevoProyectoDialog(self, self.srv, correo_pre).mostrar()
        if not d:
            return
        self.srv.crear_proyecto(d["nombre"], d["descripcion"], d["correo"], estado=d["estado"])
        self.v_buscar.set("")
        self.sel = f"p:{d['nombre']}"
        self.refrescar_todo()
        self.msg(f"✅ Proyecto «{d['nombre']}» creado" + (f" en {d['correo']}." if d["correo"] else " (sin correo)."))

    @seguro
    def accion_nuevo_correo(self):
        if not self._puedo_continuar():
            return
        if not self.srv.grupos():
            self.srv.crear_grupo()
        grupo_pre = None
        if self.sel and self.sel[:2] in ("g:", "c:"):
            grupo_pre = self.sel[2:].split("|")[0]
        d = CuentaDialog(self, "Nuevo correo", grupos=self.srv.grupos(), grupo_pre=grupo_pre).mostrar()
        if not d:
            return
        self.srv.agregar_cuenta(d["grupo"], d["correo"], d["clave"] or None)
        self.v_buscar.set("")
        self.sel = f"c:{d['grupo']}|{d['correo']}"
        self.refrescar_todo()
        self.msg(f"✅ Correo {d['correo']} agregado a {d['grupo']}.")

    @seguro
    def accion_grupos(self):
        if not self._puedo_continuar():
            return
        GruposDialog(self, self.srv).mostrar()
        self.refrescar_todo()

    @seguro
    def accion_exportar_csv(self):
        if not self._puedo_continuar():
            return
        ruta = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile="mis_correos_y_proyectos.csv",
                                            filetypes=[("Excel (CSV)", "*.csv")], title="Exportar lista de correos y proyectos")
        if not ruta:
            return
        self.srv.exportar_csv(ruta)
        self.msg(f"✅ Lista guardada en {ruta}. Ábrela con Excel (doble clic).")

    @seguro
    def accion_importar_csv(self):
        if not self._puedo_continuar():
            return
        ruta = filedialog.askopenfilename(parent=self, filetypes=[("Lista (CSV)", "*.csv")],
                                          title="Importar lista de correos y proyectos")
        if not ruta:
            return
        c, p, a = self.srv.importar_csv(ruta)
        self.refrescar_todo()
        self.msg(f"✅ Lista importada: {c} correo(s) nuevo(s), {p} proyecto(s) nuevo(s), {a} actualizado(s).")

    @seguro
    def accion_config(self):
        if not self._puedo_continuar():
            return
        d = ConfigDialog(self, self.cfg).mostrar()
        if not d:
            return
        cambio = d["ruta_datos"] != self.cfg["ruta_datos"]
        self.cfg["ruta_datos"] = d["ruta_datos"]
        self.cfg.guardar()
        if cambio:
            self._abrir_servicio()
            self.sel = None
            self._arranque()
        self.refrescar_todo()
        self.msg("Configuración guardada.")

    @seguro
    def accion_revisar(self):
        avisos = self.srv.verificar_reglas()
        if avisos:
            messagebox.showwarning("Inconsistencias", "• " + "\n• ".join(avisos), parent=self)
        else:
            messagebox.showinfo("Todo en orden", "Los datos cumplen las reglas: ningún correo repetido y todos los "
                                "proyectos tienen un correo válido (o ninguno).", parent=self)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # texto nítido en pantallas con escala
        except Exception:
            pass
        try:
            import ctypes
            # identidad propia en la barra de tareas (si no, Windows agrupa la app bajo el icono de Python)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GestorSesiones.App")
        except Exception:
            pass
    App().mainloop()
