"""
用户仓储

负责按用户名或 id 查询用户、以及创建新用户，是鉴权链路访问
`app_user` 表的唯一入口。实体与 ORM 模型的转换就地完成，
避免为一个简单对象单独引入 mapper。
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.user import User
from app.models.user import UserMySQL


class UserRepository:
    """负责用户的查询与创建"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_users(self, search: str | None = None) -> list[User]:
        """查询全部用户（管理员视图），可按用户名或昵称模糊搜索"""
        stmt = select(UserMySQL).order_by(UserMySQL.id.asc())
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(UserMySQL.username.like(pattern), UserMySQL.nickname.like(pattern))
            )
        result = await self.session.execute(stmt)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def get_by_username(self, username: str) -> User | None:
        """按用户名查询用户，登录和注册查重共用"""
        result = await self.session.execute(
            select(UserMySQL).where(UserMySQL.username == username)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, user_id: int) -> User | None:
        """按主键查询用户，供鉴权依赖校验 token 中的用户"""
        model = await self.session.get(UserMySQL, user_id)
        return self._to_entity(model) if model else None

    async def create(self, username: str, password_hash: str) -> User:
        """创建用户并 flush 以拿到自增主键，提交由调用方事务控制"""
        model = UserMySQL(username=username, password_hash=password_hash, nickname=username)
        self.session.add(model)
        await self.session.flush()
        return self._to_entity(model)

    async def update_profile(
        self, user_id: int, nickname: str | None, avatar: str | None
    ) -> User:
        """更新昵称与头像，空值归一化为 None；flush 由调用方事务提交"""
        model = await self.session.get(UserMySQL, user_id)
        model.nickname = nickname or None
        model.avatar = avatar or None
        await self.session.flush()
        return self._to_entity(model)

    async def update_password(self, user_id: int, password_hash: str) -> None:
        """更新密码哈希"""
        model = await self.session.get(UserMySQL, user_id)
        model.password_hash = password_hash
        await self.session.flush()

    async def delete(self, user_id: int) -> None:
        """删除用户（flush，提交由调用方事务控制）"""
        model = await self.session.get(UserMySQL, user_id)
        if model:
            await self.session.delete(model)
            await self.session.flush()

    @staticmethod
    def _to_entity(model: UserMySQL) -> User:
        """把 ORM 模型还原成业务实体"""
        return User(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            nickname=model.nickname,
            avatar=model.avatar,
            role=model.role,
            scope=model.scope,
            disabled=model.disabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
