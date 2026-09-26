"""对象存储服务

把用户上传的头像写入阿里云 OSS，返回可公网访问的 URL。数据库只保存 URL，
不再落 base64 数据，避免把超大的 base64 塞进 app_user.avatar 的 TEXT 列导致
「Data too long」报错。
"""

import base64
import uuid

import oss2
from starlette.concurrency import run_in_threadpool

from app.conf.app_config import app_config
from app.core.log import logger

# 按 MIME 决定 OSS 对象的扩展名，前端默认压缩成 PNG
_MIME_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}

# 头像上限 2MB（前端已压缩到 256px，实际只有几十 KB）
MAX_AVATAR_BYTES = 2 * 1024 * 1024


class OSSService:
    """封装头像上传到阿里云 OSS 的轻量服务"""

    def __init__(self):
        cfg = app_config.oss
        self._bucket_name = cfg.bucket
        self._endpoint = cfg.endpoint
        if not all(
            [cfg.endpoint, cfg.access_key_id, cfg.access_key_secret, cfg.bucket]
        ):
            self._bucket_obj = None
            return
        auth = oss2.Auth(cfg.access_key_id, cfg.access_key_secret)
        self._bucket_obj = oss2.Bucket(auth, cfg.endpoint, cfg.bucket)

    def _require_bucket(self) -> oss2.Bucket:
        if self._bucket_obj is None:
            raise ValueError(
                "OSS 未配置：请在 .env 中设置 OSS_ENDPOINT / OSS_ACCESS_KEY_ID / "
                "OSS_ACCESS_KEY_SECRET / OSS_BUCKET"
            )
        return self._bucket_obj

    @staticmethod
    def _decode_data_url(data_url: str) -> tuple[bytes, str]:
        """把 data URL 拆成图片字节与 MIME 类型"""
        if not isinstance(data_url, str) or not data_url.startswith("data:"):
            raise ValueError("头像必须是 data URL（data:image/...;base64,...）")
        header, _, encoded = data_url.partition(",")
        if not encoded:
            raise ValueError("头像数据为空")
        mime = header[len("data:") :].split(";")[0].strip() or "image/png"
        try:
            content = base64.b64decode(encoded, validate=False)
        except Exception as e:  # noqa: BLE001
            raise ValueError("头像 base64 解码失败") from e
        if not content:
            raise ValueError("头像数据为空")
        if len(content) > MAX_AVATAR_BYTES:
            raise ValueError("头像过大，请上传 2MB 以内的图片")
        return content, mime

    async def upload_avatar(self, user_id: int, data_url: str) -> str:
        """上传头像到 OSS，返回公网 URL"""
        content, mime = self._decode_data_url(data_url)
        bucket = self._require_bucket()
        ext = _MIME_EXT.get(mime, ".png")
        key = f"avatars/{user_id}/{uuid.uuid4().hex}{ext}"
        # oss2 是同步库，放到线程池执行，避免阻塞事件循环
        await run_in_threadpool(
            bucket.put_object, key, content, headers={"Content-Type": mime}
        )
        logger.info("已上传用户 {} 的头像到 OSS：{}", user_id, key)
        return f"https://{self._bucket_name}.{self._endpoint}/{key}"
