"""
鉴权服务

承载注册与登录的业务逻辑：查重、密码哈希、密码校验与 JWT 签发。
业务校验失败统一抛出 ValueError，由路由层转换成对应的 HTTP 状态码。
"""

from app.core.security import (
    create_access_token,
    hash_password_async,
    verify_password_async,
)
from app.entities.user import User
from app.repositories.mysql.meta.user_repository import UserRepository


class AuthService:
    """负责注册与登录的编排"""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def register(self, username: str, password: str) -> tuple[str, User]:
        """注册新用户并直接返回登录令牌"""
        existing = await self.user_repository.get_by_username(username)
        if existing:
            raise ValueError("用户名已存在")

        password_hash = await hash_password_async(password)
        user = await self.user_repository.create(username, password_hash)
        # 前面的查重 SELECT 已开启隐式事务，这里直接提交即可，不能再嵌套 session.begin()
        await self.user_repository.session.commit()

        token = create_access_token(user.id, user.role, user.scope)
        return token, user

    async def login(self, username: str, password: str) -> tuple[str, User]:
        """校验账号密码并签发令牌"""
        user = await self.user_repository.get_by_username(username)
        if not user or not await verify_password_async(password, user.password_hash):
            raise ValueError("用户名或密码错误")
        if user.disabled:
            raise ValueError("账号已被禁用")

        token = create_access_token(user.id, user.role, user.scope)
        return token, user

    async def update_profile(
        self, user_id: int, nickname: str | None, avatar: str | None
    ) -> User:
        """更新当前用户的昵称与头像，返回更新后的用户"""
        user = await self.user_repository.update_profile(user_id, nickname, avatar)
        await self.user_repository.session.commit()
        return user

    async def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> None:
        """校验原密码后更新为新密码，失败抛 ValueError 由路由转成 400"""
        user = await self.user_repository.get_by_id(user_id)
        if not user or not await verify_password_async(old_password, user.password_hash):
            raise ValueError("原密码错误")

        password_hash = await hash_password_async(new_password)
        await self.user_repository.update_password(user_id, password_hash)
        await self.user_repository.session.commit()
