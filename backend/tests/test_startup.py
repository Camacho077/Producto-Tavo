"""
Smoke test de arranque real. A diferencia del resto de la suite (que usa
TestClient in-process contra la app ya importada), este test lanza
`uvicorn` como proceso aparte —igual que en desarrollo o producción— y
hace un request HTTP real a /health.

Por qué existe: el 2026-09-14 un error de CORS reportado en el navegador
resultó ser, en realidad, que el backend no estaba corriendo — no un
problema de configuración de CORS. Un TestClient in-process no habría
detectado eso porque nunca levanta un socket real ni pasa por el proceso
de arranque completo (carga de .env, construcción de Settings, etc.).
Este test cierra ese hueco: si algo en la configuración de entorno rompe
el arranque real del proceso, falla aquí con un mensaje claro en vez de
descubrirse manualmente en el navegador.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2 as httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_el_backend_arranca_como_proceso_real_y_responde_health():
    puerto = _puerto_libre()
    proceso = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(puerto)],
        cwd=BACKEND_DIR,
        # Ese puerto al azar pasa a ser el del backend: sin esto, la guarda de
        # app/core/arranque.py (con razón) se niega a arrancar fuera del 8002.
        env={**os.environ, "PORT": str(puerto), "PYTHONIOENCODING": "utf-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    try:
        url = f"http://127.0.0.1:{puerto}/health"
        ultimo_error = None
        for _ in range(50):
            if proceso.poll() is not None:
                salida = proceso.stdout.read()
                pytest.fail(
                    f"El backend terminó antes de tiempo (código {proceso.returncode}) al arrancar. "
                    f"Salida del proceso:\n{salida}"
                )
            try:
                resp = httpx.get(url, timeout=1)
            except httpx.TransportError as exc:
                ultimo_error = exc
                time.sleep(0.2)
                continue
            assert resp.status_code == 200, f"/health respondió {resp.status_code}: {resp.text}"
            assert resp.json()["status"] == "ok"
            return

        pytest.fail(f"El backend no respondió en /health a tiempo. Último error de conexión: {ultimo_error}")
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait()
        proceso.stdout.close()  # sin esto, ResourceWarning: unclosed file
