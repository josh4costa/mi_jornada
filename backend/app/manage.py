"""Local operator commands: python -m app.manage --help."""
import argparse
import asyncio
import getpass
from sqlalchemy import select, func
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, engine
from app.models import User, UserRole, Technician, WebhookDelivery
from app.schemas.user import UserCreate
from app.services.users import sync_technician_profile
from app.core.timezone import now_utc


async def create_initial_admin(db, username, email, full_name, password):
    # Serialize the bootstrap command against other invocations in PostgreSQL.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        await db.execute(text("SELECT pg_advisory_xact_lock(71234901)"))
    if await db.scalar(select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))):
        raise ValueError("Ya existe un administrador activo. Usa la administraciÃ³n de usuarios.")
    body = UserCreate(username=username, email=email, full_name=full_name, password=password, role=UserRole.ADMIN)
    user = User(**body.model_dump(exclude={"password", "phone", "employee_number", "reminders_enabled"}), password_hash=get_password_hash(body.password))
    db.add(user)
    await db.commit()


async def run(args):
    async with AsyncSessionLocal() as db:
        if args.command == "create-admin":
            password = getpass.getpass("ContraseÃ±a del administrador (8â€“72 caracteres): ")
            if password != getpass.getpass("Confirmar contraseÃ±a: "):
                raise ValueError("Las contraseÃ±as no coinciden")
            await create_initial_admin(db, args.username, args.email, args.name, password)
            print("Administrador creado.")
        elif args.command == "repair-technicians":
            users = (await db.scalars(select(User).outerjoin(Technician).where(
                User.role == UserRole.TECHNICIAN, Technician.id.is_(None)
            ))).all()
            print(f"Perfiles faltantes: {len(users)}")
            if args.apply:
                for user in users:
                    await sync_technician_profile(db, user)
                await db.commit()
                print("Perfiles creados. No se modificaron jornadas ni tareas.")
        elif args.command == "webhooks":
            pending = await db.scalar(select(func.count(WebhookDelivery.id)).where(WebhookDelivery.delivered_at.is_(None)))
            failed = await db.scalar(select(func.count(WebhookDelivery.id)).where(WebhookDelivery.delivered_at.is_(None), WebhookDelivery.attempts >= 10))
            print(f"Pendientes: {pending}; agotaron reintentos: {failed}")
            if args.retry_failed:
                from sqlalchemy import update
                await db.execute(update(WebhookDelivery).where(WebhookDelivery.delivered_at.is_(None), WebhookDelivery.attempts >= 10).values(attempts=0, available_at=now_utc()))
                await db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin")
    admin.add_argument("--username", required=True)
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    repair = commands.add_parser("repair-technicians")
    repair.add_argument("--apply", action="store_true")
    webhooks = commands.add_parser("webhooks")
    webhooks.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    async def execute():
        try:
            await run(args)
        finally:
            await engine.dispose()
    try:
        asyncio.run(execute())
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
