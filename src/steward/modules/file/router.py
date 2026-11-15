from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
# 注意，UploadFile,File是fastapi自带的，用于处理文件上传
# 必须要有python-multipart依赖

from steward.common.deps import get_current_user
from steward.modules.auth.models import User
from steward.modules.file.schemas import FileOut
from steward.modules.file.service import FileTooLargeError, UnsupportedFileError, save_upload

# prefix 写全；main.py 里 include_router 不要再叠 prefix。
router = APIRouter(prefix="/api/v1/files", tags=["file"])


# multipart/form-data，字段名 file；必须登录，目录按 user_id 隔离。
@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    file: UploadFile = File(...),  # 这玩意就是请求体，... 表示"必填"
    current_user: User = Depends(get_current_user),
) -> FileOut:
    try:
        return await save_upload(file, current_user.id)
    except UnsupportedFileError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc
