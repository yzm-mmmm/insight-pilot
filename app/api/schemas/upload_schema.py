"""上传接口请求/响应体定义"""

from pydantic import BaseModel


class AvatarUploadRequest(BaseModel):
    """头像上传请求体：image 为前端压缩后的 data URL"""

    image: str


class AvatarUploadResponse(BaseModel):
    """头像上传成功后返回的 OSS 公网 URL"""

    url: str
