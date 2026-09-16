"""
超级管理员种子脚本

负责幂等地初始化表级权限所需的 `table_permission` 表，并把 `baimiao`
提升为超级管理员（role=admin）。密码仅在账号不存在时设置为 12345678，
避免覆盖已有密码；可用 --reset-password 强制重置。可安全重复运行。

用法：
    uv run python -m app.scripts.seed_admin [--reset-password]
"""

import argparse
import asyncio

from sqlalchemy import select, text

from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.core.security import hash_password_async
from app.models.user import UserMySQL

# 与 docker/mysql/meta.sql 保持一致；对已初始化（非全新 volume）的库幂等兜底建表
TABLE_PERMISSION_DDL = """
CREATE TABLE IF NOT EXISTS table_permission (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '权限编号',
    user_id      BIGINT NOT NULL COMMENT '用户编号',
    table_name   VARCHAR(128) NOT NULL COMMENT '表名(对应 table_info.id)',
    status       VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
    reviewed_at  DATETIME NULL COMMENT '审批时间',
    reviewed_by  BIGINT NULL COMMENT '审批人用户编号',
    UNIQUE KEY uq_perm_user_table (user_id, table_name),
    KEY idx_perm_status (status)
)
"""

ADMIN_USERNAME = "baimiao"
ADMIN_PASSWORD = "12345678"


async def seed(reset_password: bool = False):
    """初始化表结构并确保超管账号存在"""
    meta_mysql_client_manager.init()

    async with meta_mysql_client_manager.session_factory() as session:
        await session.execute(text(TABLE_PERMISSION_DDL))
        await session.commit()

        result = await session.execute(
            select(UserMySQL).where(UserMySQL.username == ADMIN_USERNAME)
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = UserMySQL(
                username=ADMIN_USERNAME,
                nickname=ADMIN_USERNAME,
                password_hash=await hash_password_async(ADMIN_PASSWORD),
                role="admin",
            )
            session.add(admin)
            await session.commit()
            print(
                f"已创建超级管理员账号 {ADMIN_USERNAME}（密码 {ADMIN_PASSWORD}，角色 admin）"
            )
        else:
            changes = []
            if admin.role != "admin":
                admin.role = "admin"
                changes.append("角色提升为 admin")
            if reset_password:
                admin.password_hash = await hash_password_async(ADMIN_PASSWORD)
                changes.append(f"密码重置为 {ADMIN_PASSWORD}")
            await session.commit()
            print(
                f"账号 {ADMIN_USERNAME} 已存在："
                + ("；".join(changes) if changes else "无需变更")
            )

    await meta_mysql_client_manager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化表级权限表并确保超管账号存在")
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="强制把 baimiao 的密码重置为 12345678",
    )
    args = parser.parse_args()
    asyncio.run(seed(reset_password=args.reset_password))
