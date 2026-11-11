"""
Authentication endpoints for QCanvas.
Handles user registration, login, and authentication.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.config.settings import settings
from app.core.middleware import limiter
from app.models.database_models import User, UserRole, OtpPurpose
from app.models.schemas import (
    AdminApprovalRequest,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    RegisterResponse,
    ErrorResponse,
    EmailRequest,
    OtpVerifyRequest,
    OtpSendResponse,
    OtpVerifyResponse,
    PasswordResetCompleteRequest,
    MessageResponse,
    UpdateProfileRequest,
    UpdateProfileResponse,
)
from app.services.otp_service import OTPService
from app.services.email_service import EmailService
from app.utils.jwt_auth import create_access_token, verify_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat(),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        bio=user.bio,
    )


def _request_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" if local else "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}" if domain else masked_local


def _ensure_registration_availability(payload: UserRegisterRequest, db: Session) -> tuple[str, str]:
    normalized_email = payload.email.strip().lower()

    existing_email = db.query(User).filter(User.email == normalized_email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    existing_username = db.query(User).filter(User.username == payload.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    return normalized_email, payload.username


def _create_user_record(
    db: Session,
    payload: UserRegisterRequest,
    role: UserRole,
    is_active: bool,
    is_verified: bool,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=payload.email.strip().lower(),
        username=payload.username,
        full_name=payload.full_name,
        role=role,
        is_active=is_active,
        is_verified=is_verified,
    )
    user.set_password(payload.password)
    db.add(user)
    return user


def _build_admin_approval_link(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/admin/approve?token={token}"


def _otp_error_to_http(error_code: str) -> HTTPException:
    mapping = {
        "cooldown_active": (429, "Please wait before requesting another OTP"),
        "challenge_not_found": (410, "OTP challenge not found or inactive"),
        "otp_expired": (410, "OTP has expired"),
        "otp_locked": (423, "Too many incorrect attempts"),
        "otp_invalid": (400, "Invalid OTP code"),
        "delivery_failed": (500, "Unable to deliver OTP email"),
        "reset_session_not_found": (401, "Invalid reset token"),
        "reset_session_expired": (410, "Reset session expired"),
        "user_not_found": (404, "User not found"),
    }
    status_code, detail = mapping.get(error_code, (400, "Request could not be completed"))
    return HTTPException(status_code=status_code, detail=detail)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token
        db: Database session
        
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid or user not found
   """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = verify_token(token)
    # Purpose-specific tokens (e.g. admin approval links) must never act as login sessions.
    user_id = payload.get("sub") if payload and not payload.get("intent") else None

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    token_version = payload.get("tv", 0)
    if token_version != (user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired, please login again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get the current authenticated user if token is present.
    Returns None if no token or invalid token.
    """
    if not credentials:
        return None
        
    try:
        token = credentials.credentials
        payload = verify_token(token)
        user_id = payload.get("sub") if payload and not payload.get("intent") else None

        if not user_id:
            return None
        
        user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
        if not user or not user.is_active:
            return None

        token_version = payload.get("tv", 0)
        if token_version != (user.token_version or 0):
            return None
            
        return user
    except Exception:
        return None



@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Email or username already exists"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
@limiter.limit("10/minute")
def register(request: Request, payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    - **email**: Valid email address (must be unique)
    - **username**: Username (must be unique, 3-100 chars)
    - **password**: Password (minimum 8 characters)
    - **full_name**: User's full name
    
    Returns JWT access token and user details.
    """
    # Validate password strength
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    _ensure_registration_availability(payload, db)
    
    # Create new user
    user = _create_user_record(
        db=db,
        payload=payload,
        role=UserRole.USER,
        is_active=True,
        is_verified=not settings.AUTH_EMAIL_OTP_ENABLED,
    )
    if settings.AUTH_EMAIL_OTP_ENABLED:
        user.is_verified = False
    
    # Save to database
    db.commit()
    db.refresh(user)
    
    user_response = _to_user_response(user)

    if settings.AUTH_EMAIL_OTP_ENABLED:
        otp_result = OTPService.issue_signup_otp(
            db=db,
            user=user,
            request_ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        if not otp_result.get("success"):
            raise _otp_error_to_http(otp_result.get("error", "delivery_failed"))

        return RegisterResponse(
            verification_required=True,
            message=f"Verification code sent to {_mask_email(user.email)}",
            user=user_response,
        )

    # Backward-compatible behavior when OTP is disabled.
    access_token = create_access_token(data={"sub": str(user.id), "tv": user.token_version or 0})
    return RegisterResponse(
        verification_required=False,
        message="Registration successful",
        access_token=access_token,
        token_type="bearer",
        user=user_response,
    )


@router.post(
    "/admin/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Email or username already exists"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Unable to send admin approval email"},
    }
)
@limiter.limit("5/minute")
def register_admin(request: Request, payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new admin account that must be approved by the master admin."""
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )

    _ensure_registration_availability(payload, db)

    user = _create_user_record(
        db=db,
        payload=payload,
        role=UserRole.ADMIN,
        is_active=False,
        is_verified=False,
    )

    approval_token = create_access_token(
        data={"sub": str(user.id), "intent": "admin_approval"},
        expires_delta=timedelta(hours=24),
    )
    approval_link = _build_admin_approval_link(approval_token)

    email_result = EmailService.send_admin_approval_request(
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        approval_link=approval_link,
    )

    if not email_result.success:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=email_result.error or "Unable to send admin approval email",
        )

    db.commit()
    db.refresh(user)

    return RegisterResponse(
        verification_required=True,
        message="Admin signup request submitted for approval",
        user=_to_user_response(user),
    )


@router.post(
    "/admin/approve",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or expired approval token"},
        404: {"model": ErrorResponse, "description": "User not found"},
    }
)
def approve_admin(payload: AdminApprovalRequest, db: Session = Depends(get_db)):
    """Activate a pending admin account after master admin approval."""
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approval token is required")

    token_payload = verify_token(token)
    if not token_payload or token_payload.get("intent") != "admin_approval":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired approval token")

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid approval token payload")

    user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approval token does not belong to an admin account")

    if user.is_active and user.is_verified:
        return MessageResponse(message="Admin account is already approved")

    user.is_active = True
    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # Best-effort notification: approval remains successful even if email delivery fails.
    approved_email_result = EmailService.send_admin_approved_notification(
        full_name=user.full_name,
        username=user.username,
        email=user.email,
    )
    if not approved_email_result.success:
        print(f"[Auth] Approved admin notification email failed for {user.email}: {approved_email_result.error}")

    return MessageResponse(message="Admin account approved successfully")


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"}
    }
)
@limiter.limit("20/minute")
def login(request: Request, payload: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token and user details.
    """
    # Find user by email
    user = db.query(User).filter(
        User.email == payload.email.strip().lower(),
        User.deleted_at == None
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not user.verify_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    if settings.AUTH_EMAIL_OTP_ENABLED and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    # Update last login time
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "tv": user.token_version or 0})
    
    # Prepare user response
    user_response = _to_user_response(user)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )


@router.post("/signup/otp/send", response_model=OtpSendResponse)
@limiter.limit("5/minute")
def send_signup_otp(request: Request, payload: EmailRequest, db: Session = Depends(get_db)):
    if not settings.AUTH_EMAIL_OTP_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP flow disabled")

    user = db.query(User).filter(User.email == payload.email.strip().lower(), User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already verified")

    result = OTPService.issue_signup_otp(
        db=db,
        user=user,
        request_ip=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.get("success"):
        raise _otp_error_to_http(result.get("error", "delivery_failed"))

    return OtpSendResponse(
        message=f"Verification code sent to {_mask_email(user.email)}",
        cooldown_seconds=result["cooldown_seconds"],
        expires_in_seconds=result["expires_in_seconds"],
        attempts_remaining=result["attempts_remaining"],
        verification_required=True,
    )


@router.post("/signup/otp/resend", response_model=OtpSendResponse)
@limiter.limit("5/minute")
def resend_signup_otp(request: Request, payload: EmailRequest, db: Session = Depends(get_db)):
    return send_signup_otp(request=request, payload=payload, db=db)


@router.post("/signup/otp/verify", response_model=OtpVerifyResponse)
@limiter.limit("10/minute")
def verify_signup_otp(request: Request, payload: OtpVerifyRequest, db: Session = Depends(get_db)):
    if not settings.AUTH_EMAIL_OTP_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP flow disabled")

    otp = payload.otp.strip()
    if not (otp.isdigit() and len(otp) == 6):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP must be a 6-digit numeric code")

    user = db.query(User).filter(User.email == payload.email.strip().lower(), User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already verified")

    result = OTPService.verify_otp(
        db=db,
        user=user,
        purpose=OtpPurpose.SIGNUP_VERIFY,
        otp=otp,
        request_ip=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.get("success"):
        raise _otp_error_to_http(result.get("error", "otp_invalid"))

    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id), "tv": user.token_version or 0})
    return OtpVerifyResponse(
        message="Email verified successfully",
        verified=True,
        access_token=access_token,
        token_type="bearer",
        user=_to_user_response(user),
    )


@router.post("/password-reset/otp/send", response_model=MessageResponse)
@limiter.limit("5/minute")
def send_password_reset_otp(request: Request, payload: EmailRequest, db: Session = Depends(get_db)):
    if not settings.AUTH_EMAIL_OTP_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP flow disabled")

    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email, User.deleted_at == None, User.is_active == True).first()

    if user:
        OTPService.issue_password_reset_otp(
            db=db,
            user=user,
            request_ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

    return MessageResponse(message="If the account exists, a reset code has been sent")


@router.post("/password-reset/otp/verify", response_model=OtpVerifyResponse)
@limiter.limit("10/minute")
def verify_password_reset_otp(request: Request, payload: OtpVerifyRequest, db: Session = Depends(get_db)):
    if not settings.AUTH_EMAIL_OTP_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP flow disabled")

    otp = payload.otp.strip()
    if not (otp.isdigit() and len(otp) == 6):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP must be a 6-digit numeric code")

    user = db.query(User).filter(User.email == payload.email.strip().lower(), User.deleted_at == None, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset code")

    result = OTPService.verify_otp(
        db=db,
        user=user,
        purpose=OtpPurpose.PASSWORD_RESET,
        otp=otp,
        request_ip=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if not result.get("success"):
        raise _otp_error_to_http(result.get("error", "otp_invalid"))

    return OtpVerifyResponse(
        message="OTP verified. You can now reset your password",
        verified=True,
        reset_token=result.get("reset_token"),
        expires_in_seconds=result.get("reset_expires_in_seconds"),
    )


@router.post("/password-reset/complete", response_model=MessageResponse)
@limiter.limit("10/minute")
def complete_password_reset(
    request: Request,
    payload: PasswordResetCompleteRequest,
    db: Session = Depends(get_db)
):
    if not settings.AUTH_EMAIL_OTP_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP flow disabled")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters long")

    result = OTPService.complete_password_reset(
        db=db,
        reset_token=payload.reset_token,
        new_password=payload.new_password,
    )
    if not result.get("success"):
        raise _otp_error_to_http(result.get("error", "reset_session_not_found"))

    return MessageResponse(message="Password reset completed successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    }
)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information.
    
    Requires valid JWT token in Authorization header:
    `Authorization: Bearer <token>`
    
    Returns user details without sensitive information.
    """
    return _to_user_response(current_user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse, "description": "Invalid or expired token"}},
)
def refresh_access_token(current_user: User = Depends(get_current_user)):
    """
    Exchange a still-valid access token for a fresh one (sliding session).

    The frontend calls this on IDE load and periodically while the tab is open,
    so active users are never logged out mid-session. Tokens are still revocable:
    bumping `token_version` (password reset) invalidates every issued token.
    """
    access_token = create_access_token(
        data={"sub": str(current_user.id), "tv": current_user.token_version or 0}
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=_to_user_response(current_user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout():
    """
    Logout endpoint (stateless JWT, so just a placeholder).
    
    In a stateless JWT system, logout is handled on the client side
    by deleting the token. This endpoint exists for API completeness.
    
    For production, consider implementing token blacklisting with Redis.
    """
    return {"message": "Successfully logged out"}


@router.put(
    "/me",
    response_model=UpdateProfileResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Username already taken"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    }
)
def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the current authenticated user's profile.

    Updatable fields:
    - **full_name**: User's display name
    - **username**: Unique username (must not be taken by another user)
    - **bio**: Short bio (stored client-side, echoed back in response)

    Requires valid JWT token in Authorization header.
    """
    # Check username uniqueness if changing it
    if request.username and request.username != current_user.username:
        existing = db.query(User).filter(
            User.username == request.username,
            User.id != current_user.id,
            User.deleted_at == None
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = request.username

    if request.full_name:
        current_user.full_name = request.full_name

    if request.bio is not None:
        current_user.bio = request.bio

    db.commit()
    db.refresh(current_user)

    return UpdateProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat(),
        last_login_at=current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        bio=current_user.bio,
    )

