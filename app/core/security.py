"""
安全工具

集中提供密码哈希与 JWT 签发/校验能力。bcrypt 是 CPU 密集操作，
异步路径统一通过线程池执行，避免阻塞事件循环拖慢 SSE 流式响应。
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet
from starlette.concurrency import run_in_threadpool

from app.conf.app_config import app_config


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def hash_password_async(password: str) -> str:
    """线程池内执行密码哈希，避免阻塞事件循环"""
    return await run_in_threadpool(hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    """线程池内执行密码校验，避免阻塞事件循环"""
    return await run_in_threadpool(verify_password, password, password_hash)


def create_access_token(user_id: int, role: str, scope: dict | None) -> str:
    """签发 JWT，claims 中带上用户 id、角色和预留的数据权限范围"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=app_config.jwt.expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "scope": scope,
        "exp": expire,
    }
    return jwt.encode(
        payload, app_config.jwt.secret_key, algorithm=app_config.jwt.algorithm
    )


def decode_access_token(token: str) -> dict:
    """校验并解析 JWT，失败时抛出异常由调用方转成 401"""
    return jwt.decode(
        token, app_config.jwt.secret_key, algorithms=[app_config.jwt.algorithm]
    )


def _fernet() -> Fernet:
    """由 JWT 密钥派生一个 Fernet 对称密钥，用于可逆加密数据源密码"""
    digest = hashlib.sha256(app_config.jwt.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def obfuscate_secret(plain: str) -> str:
    """可逆加密数据源连接密码，连接源库时需要还原明文

    注意：任何可逆方案都意味着应用本身能读到明文（这是连接所必需的），
    生产环境应改用 KMS/Secret Manager。密钥随 JWT 密钥变化，变更后旧密文失效。
    """
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def deobfuscate_secret(cipher: str) -> str:
    """还原被 obfuscate_secret 加密的明文密码"""
    return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
