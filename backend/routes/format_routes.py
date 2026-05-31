from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, CurrentUser
from utils.user_paths import resolve_under_root
from utils.sql_format import format_sql
from utils.secret_scrub import scrub

router = APIRouter()


class FormatRequest(BaseModel):
    path: str
    file_path: str
    content: str


@router.post("/api/format-sql")
async def format_sql_endpoint(req: FormatRequest, user: CurrentUser = Depends(get_current_user)):
    worktree = resolve_under_root(user.sub, req.path)
    result = format_sql(worktree, req.content)
    if not result.get("ok"):
        return {"ok": False, "error": scrub(result.get("error", "format failed"))}
    return {"ok": True, "formatted": result["formatted"]}
