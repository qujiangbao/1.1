"""RBAC Models — P4 基于角色的访问控制 (Database Architecture V1.0)

五表:
  users            — 系统用户
  roles            — 角色定义
  permissions      — 权限定义
  user_roles       — 用户-角色关联
  role_permissions — 角色-权限关联

约束:
  - 不改变 Supervisor 架构
  - 不改变 Agent 接口
  - 兼容 Database Architecture V1.0 映射规则"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey
from app.database.session import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(200))
    park_id = Column(String(50))
    data_scope = Column(String(50), default="all")   # P5: 数据隔离范围 (all / park)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(String(50), primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100))
    description = Column(Text)


class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(String(50), primary_key=True)
    code = Column(String(100), unique=True, nullable=False)
    resource_type = Column(String(50), nullable=False)  # agent / api / tool / dashboard
    resource_name = Column(String(200))
    action = Column(String(50), default="execute")        # read / write / execute


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(String(50), ForeignKey("users.user_id"), primary_key=True)
    role_id = Column(String(50), ForeignKey("roles.role_id"), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(String(50), ForeignKey("roles.role_id"), primary_key=True)
    permission_id = Column(String(50), ForeignKey("permissions.permission_id"), primary_key=True)


# ═══ 种子数据 ═══

ROLE_SEEDS = [
    ("role-super-admin",    "super_admin",         "超级管理员"),
    ("role-park-manager",   "park_manager",        "产业园经理"),
    ("role-investment-mgr", "investment_manager",  "招商经理"),
    ("role-policy-mgr",     "policy_manager",      "政策经理"),
    ("role-service",        "enterprise_service",  "企业服务"),
    ("role-viewer",         "viewer",              "只读用户"),
]

PERMISSION_SEEDS = [
    # Agent 执行权限
    ("perm-agent-investment", "agent:investment", "agent", "InvestmentAgent", "execute"),
    ("perm-agent-policy",     "agent:policy",     "agent", "PolicyAgent", "execute"),
    ("perm-agent-industry",   "agent:industry",   "agent", "IndustryAgent", "execute"),
    ("perm-agent-risk",       "agent:risk",       "agent", "RiskAgent", "execute"),
    ("perm-agent-service",    "agent:service",    "agent", "EnterpriseServiceAgent", "execute"),
    ("perm-agent-bi",         "agent:bi",         "agent", "BIAgent", "execute"),
    # API 访问权限
    ("perm-api-chat",         "api:chat",         "api", "/agent/chat", "read"),
    ("perm-api-trace",        "api:trace",        "api", "/agent/task/*/trace", "read"),
    ("perm-api-stream",       "api:stream",       "api", "/agent/stream/*", "read"),
    ("perm-api-investment",   "api:investment",   "api", "/investment/*", "read"),
    ("perm-api-policy",       "api:policy",       "api", "/policy/*", "read"),
    ("perm-api-risk",         "api:risk",         "api", "/risk/*", "read"),
    ("perm-api-dashboard",    "api:dashboard",    "api", "/dashboard/*", "read"),
    ("perm-api-admin",        "api:admin",        "api", "/admin/*", "write"),
]

# 角色-权限关联 (role_name → [permission_codes])
ROLE_PERMISSION_MAP = {
    "super_admin":         ["*"],  # 所有权限
    "park_manager":        ["*"],
    "investment_manager":  ["agent:investment", "agent:industry", "agent:risk", "agent:bi",
                            "api:chat", "api:trace", "api:stream",
                            "api:investment", "api:risk", "api:dashboard"],
    "policy_manager":      ["agent:policy", "agent:bi",
                            "api:chat", "api:trace", "api:stream",
                            "api:policy", "api:dashboard"],
    "enterprise_service":  ["agent:service", "agent:bi",
                            "api:chat", "api:trace", "api:stream",
                            "api:dashboard"],
    "viewer":              ["agent:bi",
                            "api:chat", "api:dashboard"],
}


async def seed_rbac_data(db_session):
    """种子数据插入 (幂等 — 存在则跳过)"""
    from sqlalchemy import select

    # Roles
    for role_id, name, display_name in ROLE_SEEDS:
        existing = await db_session.execute(
            select(Role).where(Role.role_id == role_id)
        )
        if existing.scalar_one_or_none() is None:
            db_session.add(Role(role_id=role_id, name=name, display_name=display_name))

    # Permissions
    for perm_id, code, res_type, res_name, action in PERMISSION_SEEDS:
        existing = await db_session.execute(
            select(Permission).where(Permission.permission_id == perm_id)
        )
        if existing.scalar_one_or_none() is None:
            db_session.add(Permission(
                permission_id=perm_id, code=code,
                resource_type=res_type, resource_name=res_name, action=action,
            ))

    await db_session.flush()

    # Role-Permission mapping
    for role_name, perm_codes in ROLE_PERMISSION_MAP.items():
        role = await db_session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role.scalar_one_or_none()
        if role is None:
            continue

        if "*" in perm_codes:
            # 所有权限
            all_perms = await db_session.execute(select(Permission))
            for perm in all_perms.scalars().all():
                existing = await db_session.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.role_id,
                        RolePermission.permission_id == perm.permission_id,
                    )
                )
                if existing.scalar_one_or_none() is None:
                    db_session.add(RolePermission(
                        role_id=role.role_id, permission_id=perm.permission_id,
                    ))
        else:
            for code in perm_codes:
                perm = await db_session.execute(
                    select(Permission).where(Permission.code == code)
                )
                perm = perm.scalar_one_or_none()
                if perm is None:
                    continue
                existing = await db_session.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.role_id,
                        RolePermission.permission_id == perm.permission_id,
                    )
                )
                if existing.scalar_one_or_none() is None:
                    db_session.add(RolePermission(
                        role_id=role.role_id, permission_id=perm.permission_id,
                    ))

    # Default admin user
    import bcrypt
    admin_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    existing_admin = await db_session.execute(
        select(User).where(User.username == "admin")
    )
    if existing_admin.scalar_one_or_none() is None:
        db_session.add(User(
            user_id="user-admin-001",
            username="admin",
            password_hash=admin_hash,
            display_name="系统管理员",
            is_active=True,
        ))
        await db_session.flush()
        # Assign super_admin role
        super_role = await db_session.execute(
            select(Role).where(Role.name == "super_admin")
        )
        super_role = super_role.scalar_one_or_none()
        if super_role:
            db_session.add(UserRole(
                user_id="user-admin-001", role_id=super_role.role_id,
            ))

    await db_session.commit()
