"""
Script: alta de un nuevo cliente (tenant) en el sistema.

Qué hace:
    Crea el registro de Tenant con su configuración de personalización
    (colores, logo, plan contratado) y el usuario administrador inicial
    de esa empresa.

Cuándo correrlo:
    Una vez, al cerrar un cliente nuevo — reemplaza la tarea manual de
    "montar el sistema desde cero" por un solo comando.

Uso:
    python alta_tenant.py --empresa "Restaurante El Fogón" --plan estandar \
        --admin-email admin@elfogon.com --admin-password "clave-temporal" \
        --color-primario "#7A2E2E"

Variables de entorno requeridas:
    DATABASE_URL (la toma automáticamente de app.core.config si no se pasa)
"""
import argparse
import sys
from pathlib import Path

# Evita UnicodeEncodeError al imprimir ✔/✘ en consolas de Windows que no
# usan UTF-8 por defecto (cp1252, etc.).
sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db.models import Tenant
from app.modules.seguridad.models import Usuario, Rol
from app.core.security import hash_password
from app.core.catalogo_permisos import ROLES_DE_EJEMPLO


def main():
    parser = argparse.ArgumentParser(description="Alta de un nuevo tenant (cliente)")
    parser.add_argument("--empresa", required=True)
    parser.add_argument("--plan", default="basico", choices=["basico", "estandar", "pro_ia"])
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    # Sin color por defecto (2026-10-02): la paleta es monocromática y una
    # empresa nueva se ve en grises. El color de marca es una decisión de cada
    # cliente; antes el valor por defecto era un azul (#1E3A5F) y toda empresa
    # creada con este script, incluida la demo de setup.ps1, nacía azul.
    parser.add_argument("--color-primario", default=None)
    parser.add_argument(
        "--si-no-existe",
        action="store_true",
        help="Si ya hay un usuario con ese correo, no hace nada y termina bien (lo usa automatizaciones/setup.*)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.si_no_existe:
            existente = db.query(Usuario).filter(Usuario.email == args.admin_email.strip().lower()).first()
            if existente is not None:
                print(f"✔ El usuario {args.admin_email} ya existe (empresa id={existente.tenant_id}); no se crea nada")
                return
        tenant = Tenant(
            nombre_empresa=args.empresa,
            plan=args.plan,
            theme_config={"color_primario": args.color_primario} if args.color_primario else {},
            modulos_activos=[],
        )
        db.add(tenant)
        db.flush()  # para obtener tenant.id antes del commit

        # Mismo alta que el registro: Administrador con acceso total y los roles
        # de ejemplo (Cajero, Bodega) con permisos limitados.
        rol_admin = Rol(
            tenant_id=tenant.id, nombre="Administrador", descripcion="Acceso total", es_administrador=True
        )
        db.add(rol_admin)
        for nombre, (descripcion, permisos) in ROLES_DE_EJEMPLO.items():
            db.add(Rol(tenant_id=tenant.id, nombre=nombre, descripcion=descripcion, permisos=permisos))
        db.flush()

        admin = Usuario(
            tenant_id=tenant.id,
            nombre_completo="Administrador",
            email=args.admin_email.strip().lower(),
            hashed_password=hash_password(args.admin_password),
            rol_id=rol_admin.id,
        )
        db.add(admin)
        db.commit()

        print(f"✔ Tenant '{args.empresa}' creado (id={tenant.id}), plan={args.plan}")
        print(f"✔ Usuario administrador: {args.admin_email}")
    except IntegrityError:
        db.rollback()
        print(f"✘ Ya existe un usuario con el correo '{args.admin_email}' en otro tenant (el correo debe ser único en todo el sistema)")
        raise
    except Exception as e:
        db.rollback()
        print(f"✘ Error creando el tenant: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
