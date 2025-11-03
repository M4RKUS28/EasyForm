"""
Authentication service for handling user login,
registration, and Google OAuth callback.
"""
import base64
import secrets
import uuid
from logging import Logger
from typing import Optional
from urllib.parse import quote_plus



import requests
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import auth as auth_schema
from ..api.schemas import user as user_schema
from ..config import settings
from ..core import security
from ..core.enums import AccessLevel
from ..core.security import oauth
from ..db.crud import users_crud
from ..db.crud import collection_crud

from ..core.enums import UserRole


logger = Logger(__name__)

async def login_user(form_data: OAuth2PasswordRequestForm, db: AsyncSession, response: Response) -> auth_schema.APIResponseStatus:
    """Authenticates a user and returns an access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Username and password are required")

    # Check if the user exists and verify the password
    user = await users_crud.get_user_by_username(db, form_data.username)
    if not user:
        user = await users_crud.get_user_by_email(db, form_data.username)

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")
    if not user.is_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Inactive user")

    cookie_data = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "email": user.email,
        "access_level": AccessLevel.READ_WRITE.value
        }

    # Generate access token with user details
    access_token = security.create_access_token(
        data=cookie_data
    )

    refresh_token_value = security.create_refresh_token(
        data=cookie_data
    )

    # Save last login time
    previous_last_login = user.last_login
    await users_crud.update_user_last_login(db, user_id=str(user.id))


    # Set the access token in the response cookie
    security.set_access_cookie(response, access_token)
    # Set the refresh token in the response cookie
    security.set_refresh_cookie(response, refresh_token_value)

    return auth_schema.APIResponseStatus(status="success",
                                         msg="Successfully logged in",
                                         data={ "last_login": previous_last_login.isoformat()})


async def register_user(user_data: user_schema.UserCreate, db: AsyncSession, response: Response) -> auth_schema.APIResponseStatus:
    """Registers a new user and returns the created user data."""
    
    # Check if username from incoming data (user_data.username) already exists in the DB
    db_user_by_username = await users_crud.get_user_by_username(db, user_data.username)
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    # Check if email from incoming data (user_data.email) already exists in the DB
    db_user_by_email = await users_crud.get_user_by_email(db, user_data.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Generate a unique string ID
    user_id = None
    while True:
        user_id = str(uuid.uuid4())
        if not await users_crud.get_user_by_id(db, user_id):
            break
    
    # Create the user in the database
    # When a user is registered, created_at and last_login are set by default in the model
    new_user = await users_crud.create_user(
        db = db,
        user_id = user_id,
        username = user_data.username,
        email = user_data.email,
        hashed_password = security.get_password_hash(user_data.password),
        profile_image_url = user_data.profile_image_url,
        theme = user_data.theme,
        language = getattr(user_data, "language", None) or "en",
    )

    # Create default collections for the new user
    await collection_crud.create_default_collections(db, user_id)

    cookie_data = {
        "sub": new_user.username,
        "user_id": new_user.id,
        "role": UserRole.USER.value,
        "email": new_user.email,
        "access_level": AccessLevel.READ_WRITE.value
        }

    # Set access cookie
    access_token = security.create_access_token(data=cookie_data)

    # Set the access token in the response cookie
    refresh_token_value = security.create_refresh_token(data=cookie_data)

    # Set the access token in the response cookie
    security.set_access_cookie(response, access_token)
    # Set the refresh token in the response cookie
    security.set_refresh_cookie(response, refresh_token_value)

    return auth_schema.APIResponseStatus(status="success",
                                        msg="Successfully logged in")



async def logout_user(response: Response) -> auth_schema.APIResponseStatus:
    """Logs out a user by clearing the access and refresh tokens."""
    
    # Disable the user session in the database if needed
    #diable_token(db, response)

    # Clear the access token cookie
    security.clear_access_cookie(response)
    # Clear the refresh token cookie
    security.clear_refresh_cookie(response)

    return auth_schema.APIResponseStatus(status="success", msg="Successfully logged out")

async def refresh_token(token: Optional[str], db: AsyncSession, response: Response) -> auth_schema.APIResponseStatus:
    """Refreshes the access token for a user."""

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: token missing",
        )
    
    # Verify the token and extract user ID
    payload = security.verify_token(token)
    user_id = payload["user_id"]

    # Fetch the user from the database using the user ID
    user = await users_crud.get_active_user_by_id(db, user_id)

    if user is None:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
    )


    data = security.decode_token(token)
    data["sub"] = user.username
    access_token = security.create_access_token(data=data)

    # Set the access token in the response cookie
    security.set_access_cookie(response, access_token)

    return auth_schema.APIResponseStatus(status="success", msg="")



def _extract_detail_message(detail: Optional[object]) -> Optional[str]:
    """Extracts a human-readable message from an HTTPException detail payload."""
    if not detail:
        return None

    if isinstance(detail, str):
        return detail

    if isinstance(detail, dict):
        for key in ("msg", "detail", "message"):
            value = detail.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                joined = " ".join(str(item) for item in value if item)
                if joined:
                    return joined

    if isinstance(detail, list):
        messages = []
        for item in detail:
            message = _extract_detail_message(item)
            if message:
                messages.append(message)
        if messages:
            return " ".join(messages)

    return str(detail)


def _build_login_failed_redirect(reason: str) -> RedirectResponse:
    frontend_base_url = settings.FRONTEND_BASE_URL
    if not frontend_base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Frontend base URL is not configured."
        )

    safe_reason = quote_plus(reason) if reason else ""
    url = f"{frontend_base_url}/auth/login-failed"
    if safe_reason:
        url = f"{url}?reason={safe_reason}"
    return RedirectResponse(url=url)


async def handle_oauth_callback(request: Request, db: AsyncSession, website: str = "google"):
    """Handles the callback from OAuth after user authentication."""

    oauth_client = getattr(oauth, website, None)

    if not oauth_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=website + "OAuth client is not configured."
        )

    redirectable_statuses = {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    }

    try:
        token = await oauth_client.authorize_access_token(request)

        # Fetch user info from the token
        if website == "github":
            access_token = token.get("access_token")
            headers = {"Authorization": f"token {access_token}"}
            user_response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
            user_response.raise_for_status()
            user_info = user_response.json()
            email = user_info.get("email")
            if not email:
                emails_response = requests.get("https://api.github.com/user/emails", headers=headers, timeout=10)
                emails_response.raise_for_status()
                emails = emails_response.json()
                primary_emails = [e["email"] for e in emails if e.get("primary") and e.get("verified")]
                email = primary_emails[0] if primary_emails else None
            name = user_info.get("name") or user_info.get("login")
            picture_url = user_info.get("avatar_url")
        elif website == "google":
            user_info = token.get('userinfo')
            if not user_info or not user_info.get("email"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Could not fetch user info from {website}.")
            email = user_info["email"]
            name = user_info.get("name")
            picture_url = user_info.get("picture")
        elif website == "discord":
            access_token = token.get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = requests.get("https://discord.com/api/users/@me", headers=headers, timeout=10)
            user_response.raise_for_status()
            user_info = user_response.json()
            email = user_info.get("email")
            name = user_info.get("username")
            avatar = user_info.get("avatar")
            user_id = user_info.get("id")
            if avatar and user_id:
                picture_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"
            else:
                picture_url = None
            if not email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Could not fetch user info from {website}.")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unsupported OAuth provider: {website}")

        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Could not fetch user email from {website}.")

        db_user = await users_crud.get_user_by_email(db, email)

        if not db_user:
            logger.info("Creating new user for %s OAuth login: %s (%s)", website, email, name)
            base_username = (name.lower().replace(" ", ".")[:40] if name else (email.split("@")[0][:40] if email else "user"))
            username_candidate = base_username[:42]
            final_username = username_candidate

            while await users_crud.get_user_by_username(db, final_username):
                suffix = secrets.token_hex(3)
                final_username = f"{username_candidate[:42]}.{suffix}"

            random_password = secrets.token_urlsafe(16)
            hashed_password = security.get_password_hash(random_password)

            user_id = secrets.token_hex(16)
            db_user = await users_crud.create_user(
                db,
                user_id,
                final_username,
                email,
                hashed_password,
                is_active=True,
                role=UserRole.USER.value,
                profile_image_url=picture_url,
                language="en",
            )
            # Create default collections for the new user
            await collection_crud.create_default_collections(db, user_id)
        else:
            logger.info("Using existing user %s from database for %s OAuth login.", db_user.username, website)
            if picture_url and getattr(db_user, 'profile_image_url', None) != picture_url:
                await users_crud.update_user_profile_image(db, db_user, picture_url)

        if not db_user or not db_user.is_active:  # type: ignore
            logger.warning("Inactive user OAuth login attempt: %s", email)
            return _build_login_failed_redirect("Your account is inactive. Please contact an administrator.")

        token_data = {
            "sub": db_user.username,
            "user_id": db_user.id,
            "role": db_user.role,
            "email": db_user.email,
            "access_level": AccessLevel.READ_WRITE.value
        }

        access_token = security.create_access_token(data=token_data)
        refresh_token_value = security.create_refresh_token(data=token_data)

        await users_crud.update_user_last_login(db, user_id=str(db_user.id))

        frontend_base_url = settings.FRONTEND_BASE_URL
        if not frontend_base_url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Frontend base URL is not configured.")

        redirect_response = RedirectResponse(url=frontend_base_url)

        # Set the access & refresh token in the response cookie
        security.set_access_cookie(redirect_response, access_token)
        security.set_refresh_cookie(redirect_response, refresh_token_value)

        return redirect_response

    except HTTPException as http_exc:  # pragma: no cover - error routing
        if http_exc.status_code in redirectable_statuses:
            message = _extract_detail_message(http_exc.detail) or "Could not complete OAuth login."
            logger.warning("OAuth callback HTTPException (%s) for %s: %s", http_exc.status_code, website, message)
            return _build_login_failed_redirect(message)
        raise
    except Exception:  # pragma: no cover - error routing  # noqa: BLE001  # pylint: disable=broad-except
        logger.exception("Unexpected OAuth callback failure for %s", website)
        return _build_login_failed_redirect("Unexpected error occurred during OAuth login. Please try again later.")


