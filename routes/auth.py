import os
import hmac
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from jose import JWTError, jwt
from beanie import PydanticObjectId
import resend

from models import User, AdminUser, Order, hash_password, verify_password

# ── Logging Configuration ─────────────────────────────────
logger = logging.getLogger("CommercePrime_Auth")

# ── Environment & Security Settings ───────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "cc-eshop-super-secret-key-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Initialize Resend safely using environment variables only
resend.api_key = os.getenv("RESEND_API_KEY")

# Temporary in-memory OTP storage for pending registrations (Expires in 5 minutes)
# Format: { email: { "otp": "123456", "expires_at": timestamp, "data": {...} } }
otp_storage = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

router = APIRouter(tags=["Authentication"])


# =========================================================================
# ADMIN SCHEMAS 
# =========================================================================
class AdminLoginRequest(BaseModel):
    fullName: str
    birthday: str
    habits: str
    email: str  
    password: str


class AdminUpdateRequest(BaseModel):
    fullName: Optional[str] = Field(None, min_length=2, max_length=100)
    birthday: Optional[str] = None
    habits: Optional[str] = None
    email: Optional[str] = None 
    password: Optional[str] = Field(None, min_length=6)


# =========================================================================
# CUSTOMER USER SCHEMAS & OTP SCHEMAS
# =========================================================================
class UserRegister(BaseModel):
    fullName: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    mobile: Optional[str] = None
    birthDate: Optional[str] = None
    gender: Optional[str] = "Other"
    facebook: Optional[str] = None
    age: Optional[Any] = None


class SendOtpRequest(BaseModel):
    email: EmailStr
    registrationData: dict


class VerifyAndRegisterRequest(BaseModel):
    email: EmailStr
    otpCode: str


class UserLogin(BaseModel):
    email: str 
    password: str


class VerifyRequest(BaseModel):
    clientSequence: List[int]


class UserUpdate(BaseModel):
    fullName: Optional[str] = Field(None, min_length=2, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    mobile: Optional[str] = None
    birthDate: Optional[str] = None
    gender: Optional[str] = None
    facebook: Optional[str] = None
    avatar: Optional[str] = None
    age: Optional[Any] = None


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "_id": str(user.id),
        "fullName": user.fullName or "",
        "username": user.username or "",
        "email": user.email or "",
        "mobile": user.mobile or "",
        "birthDate": user.birthDate or "",
        "gender": user.gender or "Other",
        "facebook": user.facebook or "",
        "avatar": user.avatar or "",
        "age": user.age or "N/A",
        "membershipTier": user.membershipTier or "CC Prime",
        "accountStatus": user.status or "Active",
        "status": user.status or "Active",
        "isVerified": bool(user.isVerified),
        "is_admin": bool(user.is_admin),
        "created_at": user.created_at if hasattr(user, 'created_at') else "",
    }


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("JWT validation failed: 'sub' claim missing.")
            raise credentials_exception
        
        obj_id = PydanticObjectId(user_id)
    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {str(e)}", exc_info=True)
        raise credentials_exception

    try:
        user = await User.get(obj_id)
        if user is None:
            logger.warning(f"JWT validation failed: User {user_id} not found in database.")
            raise credentials_exception
        return user
    except Exception as e:
        logger.error(f"Database error while fetching current user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# =========================================================================
# ADMIN ROUTES (Isolated System)
# =========================================================================
@router.post("/admin/login")
async def admin_login(req: AdminLoginRequest):
    try:
        admin = await AdminUser.find_one({"email": req.email.strip()})
    except Exception as e:
        logger.error(f"Database error during admin login query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Security verification failed. Invalid credentials or mismatched personal data."
    )

    if not admin:
        logger.warning(f"Admin login failed: Account not found for email {req.email}")
        raise auth_error

    if not verify_password(admin.password, admin.salt, req.password.strip()):
        logger.warning(f"Admin login failed: Invalid password for {req.email}")
        raise auth_error

    if not hmac.compare_digest(admin.fullName.strip(), req.fullName.strip()):
        logger.warning(f"Admin login failed: Full name mismatch for {req.email}")
        raise auth_error
    
    if not hmac.compare_digest(admin.birthday.strip(), req.birthday.strip()):
        logger.warning(f"Admin login failed: Birthday mismatch for {req.email}")
        raise auth_error
    
    if not hmac.compare_digest(admin.habits.strip(), req.habits.strip()):
        logger.warning(f"Admin login failed: Habits mismatch for {req.email}")
        raise auth_error

    logger.info(f"Successful admin login for: {admin.fullName}")

    access_token = create_access_token(
        data={"sub": str(admin.id), "role": "super_admin"},
        expires_delta=timedelta(minutes=60)
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "admin_name": admin.fullName
    }


@router.put("/admin/update/{admin_id}")
async def update_admin_info(admin_id: str, update_data: AdminUpdateRequest):
    try:
        admin = await AdminUser.get(PydanticObjectId(admin_id))
    except Exception as e:
        logger.error(f"Invalid admin ID format submitted: {admin_id} - Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid admin ID format")

    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found")

    try:
        if update_data.fullName is not None:
            admin.fullName = update_data.fullName
        if update_data.birthday is not None:
            admin.birthday = update_data.birthday
        if update_data.habits is not None:
            admin.habits = update_data.habits
        if update_data.email is not None:
            admin.email = update_data.email
        if update_data.password is not None:
            hashed_pw, salt = hash_password(update_data.password)
            if isinstance(salt, bytes):
                salt = salt.hex()
            admin.password = hashed_pw
            admin.salt = salt

        await admin.save()
        logger.info(f"Admin information updated successfully for ID: {admin_id}")
        
    except Exception as e:
        logger.error(f"Database error updating admin {admin_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while updating admin data.")

    return {
        "success": True,
        "message": "Admin account information updated successfully",
        "admin": {
            "id": str(admin.id),
            "fullName": admin.fullName,
            "birthday": admin.birthday,
            "habits": admin.habits,
            "email": admin.email
        }
    }


@router.post("/admin/setup")
async def setup_initial_admin():
    try:
        exists = await AdminUser.find_one({"email": "SoarHarleyAndTeam"})
        if exists:
            return {"message": "Initial admin user already exists."}

        hashed_pw, salt = hash_password("Harley YC")
        if isinstance(salt, bytes):
            salt = salt.hex()
            
        now = datetime.now(timezone.utc).isoformat()

        new_admin = AdminUser(
            fullName="Harley YC",
            birthday="Yelrah CY",
            habits="Crying,Burning Peso",
            email="SoarHarleyAndTeam",
            password=hashed_pw,
            salt=salt,
            created_at=now
        )
        await new_admin.insert()
        logger.info("Initial admin user 'SoarHarleyAndTeam' successfully created.")
        
        return {
            "success": True,
            "message": "Initial admin user created successfully.",
            "admin_id": str(new_admin.id)
        }
    except Exception as e:
        logger.error(f"Failed to setup initial admin: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during admin setup.")


# =========================================================================
# CUSTOMER USER & LIVE EMAIL VERIFICATION ROUTES
# =========================================================================
@router.post("/send-otp", status_code=status.HTTP_200_OK)
async def send_otp(payload: SendOtpRequest):
    try:
        # Check if email is already registered in DB
        existing_email = await User.find_one({"email": payload.registrationData.get("email")})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        existing_username = await User.find_one({"username": payload.registrationData.get("username")})
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

        # Generate 6-digit OTP code
        otp = str(random.randint(100000, 999999))

        # Store in memory with 5-minute expiration
        otp_storage[payload.email] = {
            "otp": otp,
            "expires_at": time.time() + 300,
            "data": payload.registrationData
        }

        # Send email via Resend API
        params = {
            "from": "CC Ecom <onboarding@resend.dev>",
            "to": [payload.email],
            "subject": "CC Ecom Account Verification Code",
            "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; color: #111;">
                    <h2>Welcome to CC Ecom!</h2>
                    <p>Your verification code is:</p>
                    <h1 style="color: #0284c7; letter-spacing: 4px;">{otp}</h1>
                    <p>This code will expire in 5 minutes.</p>
                </div>
            """,
        }
        resend.Emails.send(params)
        logger.info(f"OTP verification code sent successfully to {payload.email}")

        return {"success": True, "message": "Verification code sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send verification email via Resend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to dispatch verification email.")


@router.post("/verify-and-register", status_code=status.HTTP_201_CREATED)
async def verify_and_register(payload: VerifyAndRegisterRequest):
    record = otp_storage.get(payload.email)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending verification found or session expired. Please register again."
        )

    if time.time() > record["expires_at"]:
        del otp_storage[payload.email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one."
        )

    if record["otp"] != payload.otpCode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code."
        )

    # OTP is valid, retrieve user data payload
    user_data = record["data"]

    try:
        hashed_pw, salt = hash_password(user_data.get("password"))
        if isinstance(salt, bytes):
            salt = salt.hex()
            
        now = datetime.now(timezone.utc).isoformat()

        new_user = User(
            email=user_data.get("email"),
            password=hashed_pw,
            salt=salt,
            username=user_data.get("username"),
            fullName=user_data.get("fullName"),
            mobile=user_data.get("mobile") or "",
            birthDate=user_data.get("birthDate") or "",
            gender=user_data.get("gender") or "Other",
            facebook=user_data.get("facebook") or "",
            avatar="",
            age=str(user_data.get("age", "N/A")),
            membershipTier="CC Prime",
            status="Active",
            isVerified=True,  # Verified via OTP
            is_admin=False,
            created_at=now,
        )

        await new_user.insert()
        logger.info(f"New customer registered and verified successfully: {new_user.email}")

        # Clean up temporary storage
        del otp_storage[payload.email]

        return {
            "success": True,
            "message": "Account successfully created and verified!",
            "user": user_to_dict(new_user),
            "userId": str(new_user.id),
            "_id": str(new_user.id),
        }

    except Exception as e:
        logger.error(f"Database error during final user creation after OTP verification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during account creation.")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    # Legacy / direct register endpoint (kept as backup or direct insert)
    try:
        existing_email = await User.find_one({"email": user_data.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        existing_username = await User.find_one({"username": user_data.username})
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

        hashed_pw, salt = hash_password(user_data.password)
        if isinstance(salt, bytes):
            salt = salt.hex()
            
        now = datetime.now(timezone.utc).isoformat()

        new_user = User(
            email=user_data.email,
            password=hashed_pw,
            salt=salt,
            username=user_data.username,
            fullName=user_data.fullName,
            mobile=user_data.mobile or "",
            birthDate=user_data.birthDate or "",
            gender=user_data.gender or "Other",
            facebook=user_data.facebook or "",
            avatar="",
            age=str(user_data.age) if user_data.age else "N/A",
            membershipTier="CC Prime",
            status="Active",
            isVerified=False,
            is_admin=False,
            created_at=now,
        )

        await new_user.insert()
        logger.info(f"New customer registered successfully: {new_user.email}")

        return {
            "success": True,
            "message": "Registration successful",
            "user": user_to_dict(new_user),
            "userId": str(new_user.id),
            "_id": str(new_user.id),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error during user registration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during registration.")


@router.post("/login")
async def login(request: Request):
    email = ""
    password = ""
    content_type = request.headers.get("content-type", "")
    
    try:
        if "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            email = form_data.get("username")
            password = form_data.get("password")
        else:
            json_data = await request.json()
            email = json_data.get("email")
            password = json_data.get("password")
    except Exception as e:
        logger.warning(f"Failed to parse login request payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid request payload")

    if not email or not password:
        logger.warning("Login failed: Missing email or password in request.")
        raise HTTPException(status_code=400, detail="Email and password are required")

    try:
        user = await User.find_one({"email": email})
    except Exception as e:
        logger.error(f"Database error during user login query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if not user:
        logger.warning(f"Customer login failed: Account not found for email {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(user.password, user.salt, password):
        logger.warning(f"Customer login failed: Invalid password for {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "Active":
        logger.warning(f"Login blocked: Account {email} is not active. Status: {user.status}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info(f"Successful customer login for: {email}")

    return {
        "success": True,
        "message": "Login successful",
        "token": access_token,
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_to_dict(user),
        "_id": str(user.id),
        "userId": str(user.id),
    }


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return user_to_dict(current_user)


@router.put("/profile")
async def update_profile(update_data: UserUpdate, current_user: User = Depends(get_current_user)):
    try:
        if update_data.username and update_data.username != current_user.username:
            existing = await User.find_one({"username": update_data.username})
            if existing:
                logger.info(f"Profile update failed: Username collision ({update_data.username}) by user {current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )
            current_user.username = update_data.username

        if update_data.fullName is not None:
            current_user.fullName = update_data.fullName
        if update_data.mobile is not None:
            current_user.mobile = update_data.mobile
        if update_data.birthDate is not None:
            current_user.birthDate = update_data.birthDate
        if update_data.gender is not None:
            current_user.gender = update_data.gender
        if update_data.facebook is not None:
            current_user.facebook = update_data.facebook
        if update_data.avatar is not None:
            current_user.avatar = update_data.avatar
        if update_data.age is not None:
            current_user.age = str(update_data.age).strip() or "N/A"

        await current_user.save()
        logger.info(f"Profile updated successfully for user ID: {current_user.id}")
        return user_to_dict(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error updating profile for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while updating profile.")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return user_to_dict(current_user)


@router.get("/{user_id}")
async def get_user_by_id(user_id: str, current_user: User = Depends(get_current_user)):
    try:
        obj_id = PydanticObjectId(user_id)
    except Exception as e:
        logger.warning(f"Invalid user ID format requested: {user_id} - Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid user ID format"
        )
    
    try:
        user = await User.get(obj_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        return user_to_dict(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error fetching user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/verify/{user_id}")
async def verify_user(user_id: str, data: VerifyRequest):
    try:
        user = await User.get(PydanticObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        user.isVerified = True
        await user.save()
        logger.info(f"User {user_id} successfully verified.")
        
        return {
            "success": True, 
            "message": "User verified successfully",
            "userId": str(user.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during verification process for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid user ID format or verification failed"
        )


@router.delete("/me")
@router.delete("/{user_id}")
async def delete_user(user_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    target_id = user_id or str(current_user.id)

    if not current_user.is_admin and target_id != str(current_user.id):
        logger.warning(f"Unauthorized deletion attempt by user {current_user.id} on target {target_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You do not have permission to delete this account"
        )

    try:
        obj_id = PydanticObjectId(target_id)
    except Exception as e:
        logger.warning(f"Invalid User ID format for deletion: {target_id} - Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid User ID format")

    try:
        target_user = await User.get(obj_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        await Order.find({"user_id": target_id}).delete()
        await target_user.delete()
        
        logger.info(f"User {target_id} and associated orders were completely deleted.")

        return {
            "success": True,
            "message": f"User {target_id} and all associated orders deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error while deleting user {target_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during account deletion.")
