"""Protección de contraseñas con DPAPI de Windows (sin bibliotecas externas).

DPAPI cifra con las credenciales del usuario de Windows que ejecuta la app:
- Otro usuario de Windows, u otro PC, NO puede descifrar lo guardado (aunque copie el archivo).
- Cualquier programa que corra con TU usuario sí podría pedirle a Windows que lo descifre;
  es la misma protección que usan navegadores y clientes de correo. No es una bóveda.

Funciones: proteger(texto) -> str (base64) · desproteger(str) -> texto · disponible() -> bool
"""
import base64
import sys


class SecretoNoDisponible(Exception):
    """No se pudo cifrar/descifrar (sistema sin DPAPI, o dato guardado por otro usuario/PC)."""


def disponible() -> bool:
    return sys.platform == "win32"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [ctypes.POINTER(_BLOB), wintypes.LPCWSTR, ctypes.POINTER(_BLOB),
                                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_BLOB)]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(_BLOB), ctypes.c_void_p, ctypes.POINTER(_BLOB),
                                            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_BLOB)]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p

    def _a_blob(datos: bytes):
        buf = ctypes.create_string_buffer(datos, len(datos))
        return _BLOB(len(datos), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    def _leer_y_liberar(blob: _BLOB) -> bytes:
        try:
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            _kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))

    def proteger(texto: str) -> str:
        entrada, _buf = _a_blob(texto.encode("utf-8"))
        salida = _BLOB()
        if not _crypt32.CryptProtectData(ctypes.byref(entrada), "GestorSesiones", None, None, None, 0, ctypes.byref(salida)):
            raise SecretoNoDisponible(f"Windows no pudo proteger el dato (error {ctypes.get_last_error()}).")
        return base64.b64encode(_leer_y_liberar(salida)).decode("ascii")

    def desproteger(protegido: str) -> str:
        try:
            crudo = base64.b64decode(protegido.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError):
            raise SecretoNoDisponible("El dato guardado está dañado.")
        entrada, _buf = _a_blob(crudo)
        salida = _BLOB()
        if not _crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(salida)):
            raise SecretoNoDisponible("Windows no pudo descifrar el dato (¿lo guardó otro usuario o PC?).")
        return _leer_y_liberar(salida).decode("utf-8")

else:
    def proteger(texto: str) -> str:
        raise SecretoNoDisponible("La protección de contraseñas solo está disponible en Windows.")

    def desproteger(protegido: str) -> str:
        raise SecretoNoDisponible("La protección de contraseñas solo está disponible en Windows.")
