import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import config
from app.core.auth import create_access_token, get_current_user
from app.core.rate_limit import check_auth_rate_limit
from app.db.models import OAuthAccount, OAuthCode, OneTimeEmailToken, RevokedToken, User, utcnow
from app.db.session import get_db
from app.services.email import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
passwords = CryptContext(schemes=["argon2"], deprecated="auto")
oauth = OAuth()
oauth.register(
    name="github",
    client_id=config.GITHUB_CLIENT_ID or None,
    client_secret=config.GITHUB_CLIENT_SECRET or None,
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email"},
)
oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID or None,
    client_secret=config.GOOGLE_CLIENT_SECRET or None,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

GENERIC_FORGOT_MESSAGE = "If an account matches that email, password reset instructions will be sent shortly."
GENERIC_RESEND_MESSAGE = "If the account needs verification, a new six-digit code will be sent shortly."
GENERIC_LOGIN_MESSAGE = "Email or password is incorrect."


class EmailInput(BaseModel):
    email: EmailStr


class SignupRequest(EmailInput):
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(EmailInput):
    password: str = Field(min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyOtpRequest(EmailInput):
    otp: str = Field(pattern=r"^\d{6}$")


class OAuthCodeRequest(BaseModel):
    code: str = Field(min_length=20, max_length=256)


class AccountProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value


def _email(value: str):
    return value.strip().lower()


def _token_hash(value: str):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _new_email_token(db: Session, user: User, purpose: str, lifetime: timedelta):
    now = utcnow()
    db.execute(
        update(OneTimeEmailToken)
        .where(
            OneTimeEmailToken.user_id == user.id,
            OneTimeEmailToken.purpose == purpose,
            OneTimeEmailToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    db.add(OneTimeEmailToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=_token_hash(raw),
        expires_at=now + lifetime,
    ))
    return raw


def _new_verification_otp(db: Session, user: User):
    now = utcnow()
    db.execute(
        update(OneTimeEmailToken)
        .where(
            OneTimeEmailToken.user_id == user.id,
            OneTimeEmailToken.purpose == "verify",
            OneTimeEmailToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    for _attempt in range(10):
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _token_hash(f"{user.id}:verify:{otp}")
        if db.scalar(select(OneTimeEmailToken.id).where(OneTimeEmailToken.token_hash == otp_hash)) is None:
            break
    else:
        raise RuntimeError("Could not generate a unique verification code.")
    db.add(OneTimeEmailToken(
        user_id=user.id,
        purpose="verify",
        token_hash=otp_hash,
        expires_at=now + timedelta(minutes=10),
    ))
    return otp


def _consume_email_token(db: Session, raw: str, purpose: str):
    token = db.scalar(
        select(OneTimeEmailToken)
        .where(OneTimeEmailToken.token_hash == _token_hash(raw), OneTimeEmailToken.purpose == purpose)
        .with_for_update()
    )
    now = utcnow()
    if token is None or token.used_at is not None or _aware(token.expires_at) <= now:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired. Request a new link and try again.")
    token.used_at = now
    return token.user


def _oauth_enabled(provider: str):
    configured = (
        config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET
        if provider == "github"
        else config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET
    )
    if not configured:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured.")


def _redirect_oauth_error(provider: str):
    # Keep the browser callback outside the /auth prefix: the Vite dev proxy
    # forwards /auth/* to FastAPI, which would otherwise turn this page into a 404.
    return RedirectResponse(f"{config.FRONTEND_URL}/oauth/callback?{urlencode({'error': provider})}", status_code=303)


def _oauth_user(db: Session, provider: str, provider_user_id: str, email: str, display_name: str | None = None):
    display_name = display_name.strip()[:80] if isinstance(display_name, str) and display_name.strip() else None
    account = db.scalar(select(OAuthAccount).where(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id,
    ))
    if account:
        return account.user
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=display_name, password_hash=None, is_verified=True)
        db.add(user)
        db.flush()
    else:
        # The provider supplied a verified address, so it can safely verify and
        # link an existing password account with the same normalized email.
        user.is_verified = True
        if not user.display_name and display_name:
            user.display_name = display_name[:80]
    db.add(OAuthAccount(user_id=user.id, provider=provider, provider_user_id=provider_user_id))
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        account = db.scalar(select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        ))
        if account:
            return account.user
        raise HTTPException(status_code=409, detail="This provider account could not be linked. Sign in with the existing account and try again.")


def _create_oauth_code(db: Session, user: User):
    raw = secrets.token_urlsafe(32)
    db.add(OAuthCode(
        user_id=user.id,
        code_hash=_token_hash(raw),
        expires_at=utcnow() + timedelta(minutes=2),
    ))
    db.commit()
    return raw


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    check_auth_rate_limit(request, "signup", limit=5, window_seconds=3600)
    email = _email(str(payload.email))
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists. Sign in or request a password reset.")
    user = User(email=email, password_hash=passwords.hash(payload.password), is_verified=False)
    db.add(user)
    try:
        db.flush()
        raw = _new_verification_otp(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists. Sign in or request a password reset.")
    background.add_task(send_verification_email, email, raw)
    return {"message": "A six-digit verification code was sent to your email. It expires in 10 minutes."}


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_auth_rate_limit(request, "login", limit=8, window_seconds=300)
    user = db.scalar(select(User).where(User.email == _email(str(payload.email))))
    if user is None or user.password_hash is None or not passwords.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_MESSAGE)
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in. You can request a new verification email.")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = _consume_email_token(db, token, "verify")
    user.is_verified = True
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/verify-otp")
def verify_email_otp(payload: VerifyOtpRequest, request: Request, db: Session = Depends(get_db)):
    check_auth_rate_limit(request, "verify-otp", limit=8, window_seconds=300)
    email = _email(str(payload.email))
    user = db.scalar(select(User).where(User.email == email))
    now = utcnow()
    record = None
    if user is not None:
        record = db.scalar(
            select(OneTimeEmailToken)
            .where(
                OneTimeEmailToken.user_id == user.id,
                OneTimeEmailToken.purpose == "verify",
                OneTimeEmailToken.token_hash == _token_hash(f"{user.id}:verify:{payload.otp}"),
                OneTimeEmailToken.used_at.is_(None),
            )
            .with_for_update()
        )
    if user is None or user.is_verified or record is None or _aware(record.expires_at) <= now:
        raise HTTPException(status_code=400, detail="That code is invalid or expired. Request a new code and try again.")
    record.used_at = now
    user.is_verified = True
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification")
def resend_verification(payload: EmailInput, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    check_auth_rate_limit(request, "resend-verification", limit=5, window_seconds=3600)
    email = _email(str(payload.email))
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and not user.is_verified:
        raw = _new_verification_otp(db, user)
        db.commit()
        background.add_task(send_verification_email, email, raw)
    return {"message": GENERIC_RESEND_MESSAGE}


@router.post("/forgot-password")
def forgot_password(payload: EmailInput, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    check_auth_rate_limit(request, "forgot-password", limit=5, window_seconds=3600)
    email = _email(str(payload.email))
    user = db.scalar(select(User).where(User.email == email, User.password_hash.is_not(None)))
    if user is not None and user.is_verified:
        raw = _new_email_token(db, user, "reset", timedelta(minutes=45))
        db.commit()
        background.add_task(send_password_reset_email, email, raw)
    return {"message": GENERIC_FORGOT_MESSAGE}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = _consume_email_token(db, payload.token, "reset")
    user.password_hash = passwords.hash(payload.new_password)
    db.commit()
    return {"message": "Password updated. You can now sign in."}


@router.get("/me")
def who_am_i(user: User = Depends(get_current_user)):
    methods = [account.provider for account in user.oauth_accounts]
    if user.password_hash:
        methods.insert(0, "email")
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name or user.email.split("@", 1)[0].replace(".", " ").replace("_", " ").title(),
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat(),
        "auth_methods": methods,
    }


@router.patch("/me")
def update_account_profile(payload: AccountProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.display_name = payload.display_name
    db.commit()
    db.refresh(user)
    return who_am_i(user)


@router.post("/logout")
def logout(
    _user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    claims = jwt.decode(credentials.credentials, config.JWT_SECRET, algorithms=["HS256"])
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    db.add(RevokedToken(jti=claims["jti"], expires_at=expires_at))
    db.commit()
    return {"message": "Signed out."}


@router.get("/exchange")
async def exchange_get_disabled():
    raise HTTPException(status_code=405, detail="Use POST to exchange the one-time OAuth code.")


@router.post("/exchange")
def exchange_oauth_code(payload: OAuthCodeRequest, request: Request, db: Session = Depends(get_db)):
    check_auth_rate_limit(request, "oauth-exchange", limit=10, window_seconds=300)
    record = db.scalar(select(OAuthCode).where(OAuthCode.code_hash == _token_hash(payload.code)).with_for_update())
    now = utcnow()
    if record is None or record.used_at is not None or _aware(record.expires_at) <= now:
        raise HTTPException(status_code=400, detail="This sign-in link is invalid or expired. Please sign in again.")
    record.used_at = now
    user = db.get(User, record.user_id)
    if user is None or not user.is_verified:
        db.commit()
        raise HTTPException(status_code=400, detail="This account could not be signed in. Please try again.")
    access_token = create_access_token(user.id)
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/github")
async def github_login(request: Request):
    _oauth_enabled("github")
    redirect_uri = f"{config.BACKEND_URL}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    _oauth_enabled("github")
    try:
        token = await oauth.github.authorize_access_token(request)
        profile_response = await oauth.github.get("user", token=token)
        profile_response.raise_for_status()
        profile = profile_response.json()
        emails_response = await oauth.github.get("user/emails", token=token)
        emails_response.raise_for_status()
        email_record = next((item for item in emails_response.json() if item.get("primary") and item.get("verified")), None)
        if email_record is None or not profile.get("id"):
            raise ValueError("A primary verified GitHub email is required.")
        user = _oauth_user(db, "github", str(profile["id"]), _email(email_record["email"]), profile.get("name") or profile.get("login"))
        code = _create_oauth_code(db, user)
        return RedirectResponse(f"{config.FRONTEND_URL}/oauth/callback?{urlencode({'code': code})}", status_code=303)
    except HTTPException:
        raise
    except Exception as exc:
        # OAuth exceptions may include authorization codes; log only the class.
        logger.warning("GitHub sign-in failed (%s).", type(exc).__name__)
        db.rollback()
        return _redirect_oauth_error("github")


@router.get("/google")
async def google_login(request: Request):
    _oauth_enabled("google")
    redirect_uri = f"{config.BACKEND_URL}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    _oauth_enabled("google")
    try:
        token = await oauth.google.authorize_access_token(request)
        profile = token.get("userinfo")
        if (
            not profile
            or not profile.get("email")
            or not profile.get("sub")
            or profile.get("email_verified") is not True
        ):
            profile = await oauth.google.userinfo(token=token)
        email_verified = profile.get("email_verified") if profile else None
        verified = email_verified is True or (isinstance(email_verified, str) and email_verified.lower() == "true")
        if not profile or not verified or not profile.get("email") or not profile.get("sub"):
            raise ValueError("A verified Google email is required.")
        user = _oauth_user(db, "google", str(profile["sub"]), _email(profile["email"]), profile.get("name"))
        code = _create_oauth_code(db, user)
        return RedirectResponse(f"{config.FRONTEND_URL}/oauth/callback?{urlencode({'code': code})}", status_code=303)
    except HTTPException:
        raise
    except Exception as exc:
        # OAuth exceptions can contain sensitive authorization codes or provider details.
        logger.warning("Google sign-in failed (%s).", type(exc).__name__)
        db.rollback()
        return _redirect_oauth_error("google")
