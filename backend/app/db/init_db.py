from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.workday import Workday, WorkdayStatus
from app.models.task import Task, TaskStatus, TaskPriority, CreatedByType
from app.core.security import get_password_hash
from app.core.timezone import today_local, now_utc
from datetime import datetime, timezone, timedelta

async def seed_demo_data(db: AsyncSession):
    # Check if admin exists
    admin_exists = await db.scalar(select(User).where(User.username == "admin"))
    if admin_exists:
        return
        
    from app.models.account_setup import TaskLocation, INITIAL_LOCATIONS, location_id
    if not await db.scalar(select(TaskLocation.id).limit(1)):
        db.add_all([TaskLocation(id=location_id(g,n), group_name=g, name=n) for g,names in INITIAL_LOCATIONS.items() for n in names])
    admin = User(
        must_change_password=False,
        username="admin",
        email="admin@mijornada.local",
        password_hash=get_password_hash("Admin2024!"),
        full_name="Administrador",
        role=UserRole.ADMIN
    )
    db.add(admin)
    await db.flush()

    techs = [
        ("juan", "Juan Pérez", "TEC-001"),
        ("pedro", "Pedro García", "TEC-002"),
        ("carlos", "Carlos Martínez", "TEC-003"),
    ]
    
    today = today_local()
    
    for idx, (username, full_name, emp_num) in enumerate(techs):
        u = User(
            must_change_password=False,
            username=username,
            email=f"{username}@mijornada.local",
            password_hash=get_password_hash("Tech2024!"),
            full_name=full_name,
            role=UserRole.TECHNICIAN
        )
        db.add(u)
        await db.flush()
        
        t = Technician(user_id=u.id, employee_number=emp_num)
        db.add(t)
        await db.flush()
        
        # Juan has an open workday
        if username == "juan":
            w = Workday(
                technician_id=t.id,
                work_date=today,
                check_in_at=datetime(today.year, today.month, today.day, 13, 58, tzinfo=timezone.utc),
                status=WorkdayStatus.OPEN
            )
            db.add(w)
            
            # Tasks for Juan
            t1 = Task(technician_id=t.id, assigned_date=today, title="Revisar instalación de cableado", location_name="PL Expo", priority=TaskPriority.HIGH, status=TaskStatus.COMPLETED, completed_at=now_utc(), created_by=admin.id, created_by_type=CreatedByType.ADMIN)
            t2 = Task(technician_id=t.id, assigned_date=today, title="Recoger equipo en proveedor", location_name="Proveedor Central", status=TaskStatus.COMPLETED, completed_at=now_utc(), created_by=admin.id, created_by_type=CreatedByType.ADMIN)
            t3 = Task(technician_id=t.id, assigned_date=today, title="Instalar equipo nuevo", location_name="PL Contry", priority=TaskPriority.HIGH, status=TaskStatus.PENDING, created_by=admin.id, created_by_type=CreatedByType.ADMIN)
            t4 = Task(technician_id=t.id, assigned_date=today, title="Entregar documentación", location_name="Oficinas Corporativas", status=TaskStatus.PENDING, created_by=admin.id, created_by_type=CreatedByType.ADMIN)
            t5 = Task(technician_id=t.id, assigned_date=today, title="Revisión de tablero eléctrico", status=TaskStatus.PENDING, created_by=u.id, created_by_type=CreatedByType.TECHNICIAN)
            db.add_all([t1, t2, t3, t4, t5])
            
        elif username == "pedro":
            # Pedro has a closed workday
            cin = datetime(today.year, today.month, today.day, 14, 3, tzinfo=timezone.utc)
            cout = datetime(today.year, today.month, today.day, 23, 11, tzinfo=timezone.utc)
            w = Workday(
                technician_id=t.id,
                work_date=today,
                check_in_at=cin,
                check_out_at=cout,
                duration_minutes=int((cout-cin).total_seconds()/60),
                status=WorkdayStatus.CLOSED
            )
            db.add(w)
            
            # Tasks for Pedro
            db.add_all([
                Task(technician_id=t.id, assigned_date=today, title="Mantenimiento preventivo 1", status=TaskStatus.COMPLETED, completed_at=now_utc(), created_by=admin.id, created_by_type=CreatedByType.ADMIN),
                Task(technician_id=t.id, assigned_date=today, title="Mantenimiento preventivo 2", status=TaskStatus.COMPLETED, completed_at=now_utc(), created_by=admin.id, created_by_type=CreatedByType.ADMIN),
                Task(technician_id=t.id, assigned_date=today, title="Mantenimiento preventivo 3", status=TaskStatus.COMPLETED, completed_at=now_utc(), created_by=admin.id, created_by_type=CreatedByType.ADMIN)
            ])
            
        elif username == "carlos":
            # Carlos has no workday today, but 2 pending tasks
            db.add_all([
                Task(technician_id=t.id, assigned_date=today, title="Revisión inicial de cliente", status=TaskStatus.PENDING, created_by=admin.id, created_by_type=CreatedByType.ADMIN),
                Task(technician_id=t.id, assigned_date=today, title="Configuración de router", status=TaskStatus.PENDING, created_by=admin.id, created_by_type=CreatedByType.ADMIN)
            ])

    await db.commit()
