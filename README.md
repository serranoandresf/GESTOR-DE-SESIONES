# Gestor de Sesiones — tus correos y sus proyectos

Aplicación de escritorio para Windows (Python + Tkinter, sin bibliotecas externas) para **organizar en qué correo
tienes cada proyecto y de qué se trata**. Nada más: no se conecta a ninguna IA ni a internet.

- Cada **proyecto** está en **un solo correo**; un correo puede tener **varios** proyectos.
- Los correos se agrupan en **Grupo 1, Grupo 2…** (los nombres los pones tú).
- Cada proyecto tiene **nombre, de qué se trata y notas**.
- Contraseña de cada correo: **opcional**, guardada cifrada con tu usuario de Windows (nunca en texto plano).
- Buscador, exportar a Excel y respaldo automático al borrar o renombrar un proyecto.

## Instalar (elige una opción)

**A) Instalador listo (no necesita Python)** — en la pestaña *Releases* de este repositorio descarga
`GestorSesiones-Setup-X.Y.Z.exe`, ábrelo y sigue el asistente. *(Lo genera GitHub Actions al publicar una versión.)*

**B) Desde el código (necesita Python 3.10+ con «tcl/tk»)**
```powershell
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
.\Instalar.bat        # copia la app a %LOCALAPPDATA%\Programs\GestorSesiones y crea los accesos con icono
```
Para actualizar: `git pull` y otra vez `.\Instalar.bat`. Tus datos no se tocan.
Para probar sin instalar: `py main.py` (o doble clic en `Iniciar_Gestor.bat`).

## Tus correos
Copia `mis_cuentas.ejemplo.json` como `mis_cuentas.json`, pon tus correos por grupo y ejecuta
`py cargar_cuentas.py` (o en la app: **👥 Gestionar correos → 📥 Cargar correos desde archivo**).
El archivo real `mis_cuentas.json` está en `.gitignore`: **no se sube al repositorio**.
En otro PC llevas tu lista con **📤 Exportar lista de correos** (sin contraseñas ni proyectos; las contraseñas
se escriben de nuevo en cada PC).

## Dónde se guardan los datos
```
<carpeta de datos>\
  proyectos\  CIMA.json ...        (nombre, de qué se trata, notas, correo)
  grupos\     Grupo_1.json ...     (correos y contraseñas cifradas)
  respaldos\                       (copia automática al renombrar o borrar un proyecto; últimos 30 por proyecto)
```
Por defecto: `D:\Javier\Documents\SISTEMA_DE_TRABAJO\DATOS` (si no existe la unidad D:, usa `Documentos\SISTEMA_DE_TRABAJO\DATOS`).
Se cambia en **⚙ Configuración**. La configuración está en `%APPDATA%\GestorSesiones\config.json`.

**Contraseñas:** viven dentro de `grupos\*.json` cifradas con DPAPI de Windows. Solo tu usuario de Windows en ese PC puede
descifrarlas: si copias la carpeta de datos a otro PC o usuario, los correos se ven pero habrá que volver a escribir las
contraseñas. Ojo: cualquier programa que corra con tu usuario podría pedirle a Windows que las descifre (es el mismo nivel
de protección que usan los navegadores); no es una bóveda. Si prefieres no guardarlas, déjalas vacías.

**Datos de versiones anteriores (1.x):** se abren sin cambios. Lo que ya no se usa (memoria, tareas, sesiones) queda
guardado en los archivos pero no se muestra.

## Publicar una versión (instalador automático)
```powershell
git tag v2.0.0
git push origin v2.0.0
```
GitHub Actions (`.github/workflows/release.yml`) ejecuta las pruebas, construye el `.exe` con icono y el instalador, y los
publica en *Releases*. También se puede lanzar a mano desde la pestaña *Actions*.

## Pruebas
```
py -m unittest discover -s tests -v
```

## Estructura del código
```
main.py                     punto de entrada
cargar_cuentas.py           carga tus correos desde mis_cuentas.json (Cargar_Mis_Cuentas.bat)
instalar.py                 instalador para tu usuario (Instalar.bat / Desinstalar.bat)
gestor_sesiones/
  config.py                 configuración (carpeta de datos)
  almacen.py                lectura/escritura atómica de JSON y respaldos
  reglas.py                 lógica (sin interfaz): correos, proyectos, búsqueda, exportar
  cuentas_lote.py           cargar/exportar listas de correos
  secretos.py               cifrado de contraseñas con DPAPI (Windows)
  ejemplo.py                datos de ejemplo
  dialogos.py, ui.py        interfaz Tkinter
tests/test_reglas.py        pruebas de la lógica
installer/                  script de Inno Setup (lo usa GitHub Actions)
```
