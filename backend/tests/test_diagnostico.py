"""Diagnóstico del entorno (app/diagnostico.py): lo corre quien clona el
repo para ver qué le falta, así que cada revisión debe decir el arreglo."""
from app import diagnostico as d
from app.core.config import Settings


def test_informe_completo_con_todas_las_secciones():
    informe = d.diagnosticar()
    assert set(informe["secciones"]) >= {
        "Archivos de configuración",
        "Variables del backend",
        "Base de datos",
        "CORS",
        "Frontend",
        "Puertos",
    }
    for items in informe["secciones"].values():
        for item in items:
            assert item["estado"] in (d.OK, d.AVISO, d.ERROR)
            if item["estado"] == d.ERROR:
                assert item["arreglo"], f"'{item['titulo']}' es un error sin arreglo"


def test_no_muestra_secretos():
    texto = str(d.diagnosticar())
    from app.core.config import settings

    assert settings.SECRET_KEY not in texto
    clave_bd = settings.DATABASE_URL.split("://", 1)[1].split("@")[0].split(":")[-1]
    assert f":{clave_bd}@" not in texto


def test_prueba_un_origen_contra_cors():
    s = Settings(ENV="development")
    permitido = d.revisar_cors(s, "http://[::1]:5175")[-1]
    rechazado = d.revisar_cors(s, "http://sitio-externo.com")[-1]
    assert permitido["estado"] == d.OK and "PERMITIDO" in permitido["titulo"]
    assert rechazado["estado"] == d.ERROR and "400" in rechazado["titulo"]
    assert "CORS_ORIGINS" in rechazado["arreglo"]


def test_sin_frontend_env_dice_que_copiar(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "RAIZ", tmp_path)
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    archivos = d.revisar_archivos_env()
    assert all(i["estado"] == d.ERROR for i in archivos)
    assert "Copy-Item frontend\.env.example frontend\.env" in archivos[1]["arreglo"]
    assert d.revisar_frontend()[0]["estado"] == d.ERROR


def test_endpoint_de_diagnostico_en_desarrollo(client):
    resp = client.get("/diagnostico", params={"origen": "http://192.168.1.50:5175"})
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert "CORS" in cuerpo["secciones"]
    assert any("PERMITIDO" in i["titulo"] for i in cuerpo["secciones"]["CORS"])
