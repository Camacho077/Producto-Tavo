"""
Autorización de tratamiento de datos en el registro (Fase 6, 2026-09-30).

Ley 1581 de 2012, art. 9, y Decreto 1377 de 2013, art. 7: la autorización
debe ser previa, expresa y poder probarse. El registro exige la casilla
(desmarcada por defecto en el frontend) y guarda qué documento, qué versión
y en qué fecha y hora se aceptó.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.legal import POLITICA_DATOS, TERMINOS, VERSIONES
from app.db.models import Tenant
from app.modules.seguridad.models import AceptacionLegal, Usuario

URL = "/api/v1/seguridad/registro"


def _datos(correo, **extra):
    return {"nombre_empresa": "Empresa Legal", "email": correo, "password": "clave-segura-123", **extra}


@pytest.mark.parametrize(
    "extra",
    [{}, {"acepta_condiciones": False}],
    ids=["sin el campo (cliente viejo)", "casilla sin marcar"],
)
def test_sin_aceptar_no_se_crea_nada_y_el_mensaje_dice_por_que(client, db_session, extra):
    correo = f"sin-aceptar-{len(extra)}@negocio.co"
    resp = client.post(URL, json=_datos(correo, **extra))

    assert resp.status_code == 422
    errores = resp.json()["errores"]
    assert any(
        e["campo"] == "acepta_condiciones" and "Política de tratamiento de datos" in e["mensaje"] for e in errores
    ), errores
    assert db_session.query(Usuario).filter(Usuario.email == correo).count() == 0
    assert db_session.query(Tenant).filter(Tenant.nombre_empresa == "Empresa Legal").count() == 0
    assert db_session.query(AceptacionLegal).filter(AceptacionLegal.email == correo).count() == 0


def test_al_aceptar_se_guarda_documento_version_y_fecha_hora(client, db_session):
    antes = datetime.now(timezone.utc) - timedelta(seconds=5)
    resp = client.post(URL, json=_datos("acepta@negocio.co", acepta_condiciones=True))
    despues = datetime.now(timezone.utc) + timedelta(seconds=5)
    assert resp.status_code == 201

    usuario = db_session.query(Usuario).filter(Usuario.email == "acepta@negocio.co").one()
    filas = db_session.query(AceptacionLegal).filter(AceptacionLegal.usuario_id == usuario.id).all()

    assert {(f.documento, f.version) for f in filas} == {
        (POLITICA_DATOS, VERSIONES[POLITICA_DATOS]),
        (TERMINOS, VERSIONES[TERMINOS]),
    }
    for f in filas:
        assert f.tenant_id == usuario.tenant_id
        assert f.email == "acepta@negocio.co"
        assert f.aceptada_en.tzinfo is not None, "la hora debe guardarse con zona horaria"
        assert antes <= f.aceptada_en <= despues


def test_la_prueba_de_aceptacion_sobrevive_si_se_elimina_el_usuario(client, db_session):
    client.post(URL, json=_datos("se-ira@negocio.co", acepta_condiciones=True))
    usuario = db_session.query(Usuario).filter(Usuario.email == "se-ira@negocio.co").one()
    tenant_id = usuario.tenant_id

    db_session.delete(usuario)
    db_session.commit()
    db_session.expire_all()

    filas = db_session.query(AceptacionLegal).filter(AceptacionLegal.tenant_id == tenant_id).all()
    assert len(filas) == 2
    assert all(f.usuario_id is None and f.email == "se-ira@negocio.co" for f in filas)
