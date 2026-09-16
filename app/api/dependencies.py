"""
FastAPI 依赖组装

集中声明 API 层需要的依赖函数，把 Session、Repository、Client 和 Service
按职责组装起来。路由层只通过 Depends 声明自己需要什么对象，具体创建细节
都收敛在这里，避免 HTTP 处理函数直接感知底层基础设施。
"""

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.security import decode_access_token
from app.entities.user import User
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.chat_repository import ChatRepository
from app.repositories.mysql.meta.data_source_repository import DataSourceRepository
from app.repositories.mysql.meta.feedback_repository import FeedbackRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.mysql.meta.permission_repository import PermissionRepository
from app.repositories.mysql.meta.user_repository import UserRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.data_source_service import DataSourceService
from app.services.permission_service import PermissionService
from app.services.query_service import QueryService
from app.services.sync_manager import SyncManager, sync_manager

# 从 Authorization 头解析 Bearer token；auto_error=False 表示缺失时返回 None，
# 由 get_current_user 统一抛出 401，而不是由框架直接返回 403
bearer_scheme = HTTPBearer(auto_error=False)


async def get_meta_session():
    """创建一次请求内使用的元数据库 Session"""

    # yield 之后的清理逻辑由 async with 负责，FastAPI 会在请求结束后继续执行退出流程
    async with meta_mysql_client_manager.session_factory() as meta_session:
        yield meta_session


async def get_meta_mysql_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> MetaMySQLRepository:
    """基于请求级 Session 创建元数据仓储"""

    return MetaMySQLRepository(session)


async def get_embedding_client() -> HuggingFaceEndpointEmbeddings:
    """获取应用启动阶段初始化好的 Embedding 客户端"""

    return embedding_client_manager.client


async def get_dw_session():
    """创建一次请求内使用的数仓 Session"""

    async with dw_mysql_client_manager.session_factory() as dw_session:
        yield dw_session


async def get_dw_mysql_repository(
    session: Annotated[AsyncSession, Depends(get_dw_session)],
) -> DWMySQLRepository:
    """基于请求级 Session 创建数仓仓储"""

    return DWMySQLRepository(session)


async def get_column_qdrant_repository() -> ColumnQdrantRepository:
    """创建字段向量检索仓储"""

    return ColumnQdrantRepository(qdrant_client_manager.client)


async def get_metric_qdrant_repository() -> MetricQdrantRepository:
    """创建指标向量检索仓储"""

    return MetricQdrantRepository(qdrant_client_manager.client)


async def get_value_es_repository() -> ValueESRepository:
    """创建字段取值全文检索仓储"""

    return ValueESRepository(es_client_manager.client)


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> UserRepository:
    """基于请求级 Session 创建用户仓储"""

    return UserRepository(session)


async def get_chat_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> ChatRepository:
    """基于请求级 Session 创建会话与消息仓储"""

    return ChatRepository(session)


async def get_feedback_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> FeedbackRepository:
    """基于请求级 Session 创建反馈仓储"""

    return FeedbackRepository(session)


async def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    """组装鉴权服务"""

    return AuthService(user_repository)


async def get_admin_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
    feedback_repository: Annotated[FeedbackRepository, Depends(get_feedback_repository)],
    permission_repository: Annotated[
        PermissionRepository, Depends(get_permission_repository)
    ],
) -> AdminService:
    """组装用户管理服务"""

    return AdminService(
        user_repository=user_repository,
        chat_repository=chat_repository,
        feedback_repository=feedback_repository,
        permission_repository=permission_repository,
    )


async def get_permission_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> PermissionRepository:
    """基于请求级 Session 创建表级权限仓储"""

    return PermissionRepository(session)


async def get_permission_service(
    permission_repository: Annotated[
        PermissionRepository, Depends(get_permission_repository)
    ],
    meta_mysql_repository: Annotated[
        MetaMySQLRepository, Depends(get_meta_mysql_repository)
    ],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    dw_mysql_repository: Annotated[DWMySQLRepository, Depends(get_dw_mysql_repository)],
) -> PermissionService:
    """组装表级权限服务"""

    return PermissionService(
        permission_repository=permission_repository,
        meta_mysql_repository=meta_mysql_repository,
        user_repository=user_repository,
        dw_mysql_repository=dw_mysql_repository,
    )


async def get_data_source_repository(
    session: Annotated[AsyncSession, Depends(get_meta_session)],
) -> DataSourceRepository:
    """基于请求级 Session 创建数据源仓储"""

    return DataSourceRepository(session)


async def get_sync_manager() -> SyncManager:
    """返回应用级同步管理器单例（生命周期在 lifespan 中绑定）"""

    return sync_manager


async def get_data_source_service(
    data_source_repository: Annotated[
        DataSourceRepository, Depends(get_data_source_repository)
    ],
    dw_mysql_repository: Annotated[DWMySQLRepository, Depends(get_dw_mysql_repository)],
    meta_mysql_repository: Annotated[
        MetaMySQLRepository, Depends(get_meta_mysql_repository)
    ],
    column_qdrant_repository: Annotated[
        ColumnQdrantRepository, Depends(get_column_qdrant_repository)
    ],
    sync_manager: Annotated[SyncManager, Depends(get_sync_manager)],
) -> DataSourceService:
    """组装数据源服务"""

    return DataSourceService(
        data_source_repository=data_source_repository,
        dw_mysql_repository=dw_mysql_repository,
        meta_mysql_repository=meta_mysql_repository,
        column_qdrant_repository=column_qdrant_repository,
        sync_manager=sync_manager,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """解析请求携带的 JWT 并返回当前登录用户

    作为受保护接口的鉴权依赖：无 token、token 失效或用户被禁用都会抛 401，
    在 SSE 开始流式输出之前就拦截未授权请求。
    """

    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="登录凭证无效或已过期")

    user = await user_repository.get_by_id(user_id)
    if user is None or user.disabled:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    return user


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """校验当前用户为管理员，否则抛 403，用于审批类接口"""

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def get_query_service(
    meta_mysql_repository: Annotated[
        MetaMySQLRepository, Depends(get_meta_mysql_repository)
    ],
    embedding_client: Annotated[
        HuggingFaceEndpointEmbeddings, Depends(get_embedding_client)
    ],
    dw_mysql_repository: Annotated[DWMySQLRepository, Depends(get_dw_mysql_repository)],
    column_qdrant_repository: Annotated[
        ColumnQdrantRepository, Depends(get_column_qdrant_repository)
    ],
    metric_qdrant_repository: Annotated[
        MetricQdrantRepository, Depends(get_metric_qdrant_repository)
    ],
    value_es_repository: Annotated[ValueESRepository, Depends(get_value_es_repository)],
) -> QueryService:
    """组装一次查询所需的业务服务"""

    # QueryService 只接收已经创建好的依赖对象，本身不关心这些对象来自 MySQL、Qdrant 还是 ES
    return QueryService(
        meta_mysql_repository=meta_mysql_repository,
        embedding_client=embedding_client,
        dw_mysql_repository=dw_mysql_repository,
        column_qdrant_repository=column_qdrant_repository,
        metric_qdrant_repository=metric_qdrant_repository,
        value_es_repository=value_es_repository,
    )
