from __future__ import annotations

from pydantic import BaseModel


# 上传结果；filename 只回显给客户端，服务端存盘用的是 file_id + 校验过的后缀。
class FileOut(BaseModel):
    file_id: str  # uuid字符串
    filename: str  # 只回显原始文件名给人看，绝不参与路径拼接
    suffix: str  # 校验过的后缀，让客户端知道服务端按哪种格式解析的
    size: int  # 实际落盘字节数，方便核对 50MB 限制
    char_count: int  # 抽出的文本长度
    token_estimate: int  # 粗略 token 估算
    # 这个类是纯出参，不需要 from_attributes=True（不是从 ORM 对象转的）
