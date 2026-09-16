"""
用户管理服务

承载管理员对用户的管理编排：列表查询、重置密码与删除（连带清理
该用户的会话、消息、反馈与表权限）。业务校验失败统一抛出 ValueError，
由路由层转换成对应的 HTTP 状态码。
"""

from app.core.security import hash_password_async
from app.entities.user import User
from app.repositories.mysql.meta.chat_repository import ChatRepository
from app.repositories.mysql.meta.feedback_repository import FeedbackRepository
from app.repositories.mysql.meta.permission_repository import PermissionRepository
from app.repositories.mysql.meta.user_repository import UserRepository


class AdminService:
    """负责用户管理的编排"""

    def __init__(
        self,
        user_repository: UserRepository,
        chat_repository: ChatRepository,
        feedback_repository: FeedbackRepository,
        permission_repository: PermissionRepository,
    ):
        self.user_repository = user_repository
        self.chat_repository = chat_repository
        self.feedback_repository = feedback_repository
        self.permission_repository = permission_repository

    async def list_users(self, search: str | None = None) -> list[User]:
        """返回全部用户（可按用户名或昵称模糊搜索）"""
        return await self.user_repository.list_users(search)

    async def reset_password(self, user_id: int, new_password: str) -> None:
        """把某用户的密码重置为新值，失败抛 ValueError 由路由转成 400"""
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValueError("用户不存在")

        password_hash = await hash_password_async(new_password)
        await self.user_repository.update_password(user_id, password_hash)
        await self.user_repository.session.commit()

    async def delete_user(self, admin: User, user_id: int) -> None:
        """删除用户并连带清理其反馈、会话消息、权限记录，失败抛 ValueError"""
        if user_id == admin.id:
            raise ValueError("不能删除自己")

        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValueError("用户不存在")

        # chat 三张表无外键约束，需按「反馈 → 消息 → 会话 → 权限 → 用户」手动级联，
        # 各仓储方法只 flush 不提交，最后统一提交一次保证原子性
        await self.feedback_repository.delete_by_user(user_id)
        await self.chat_repository.delete_by_user(user_id)
        await self.permission_repository.delete_by_user(user_id)
        await self.user_repository.delete(user_id)
        await self.user_repository.session.commit()
