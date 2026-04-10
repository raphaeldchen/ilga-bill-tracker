import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "SECRET_KEY is not set. Using an insecure default. Set it in .env before deploying.",
        stacklevel=1,
    )
    SECRET_KEY = "dev-secret-key"
COOKIE_NAME = "admin_session"
COOKIE_MAX_AGE = 8 * 60 * 60  # 8 hours
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() == "true"

_serializer = URLSafeTimedSerializer(SECRET_KEY)


def _make_cookie_value() -> str:
    return _serializer.dumps("admin")


def _validate_session(session: str | None) -> bool:
    if not session:
        return False
    try:
        _serializer.loads(session, max_age=COOKIE_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_admin(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    if not _validate_session(session):
        raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("/login")
def login_page():
    return FileResponse("static/login.html")


@router.post("/login")
async def login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if not admin_password or password != admin_password:
        return RedirectResponse(url="/login?error=1", status_code=303)

    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        _make_cookie_value(),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
    )
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@router.get("/admin")
def admin_page(session: str | None = Cookie(default=None, alias=COOKIE_NAME)):
    if not _validate_session(session):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("static/admin.html")
