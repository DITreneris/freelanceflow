from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, UserRole, Role, RolePermission, Permission

# Configuration
SECRET_KEY = "YOUR_SECRET_KEY_HERE"  # In production, use a secure env variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

# Security utilities
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Token data model
class TokenData(BaseModel):
    email: Optional[str] = None
    exp: Optional[datetime] = None

# User data models
class UserAuth(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

def verify_password(plain_password, hashed_password):
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Generate a password hash"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(db: Session, email: str) -> Optional[User]:
    """Get a user by email"""
    statement = select(User).where(User.email == email)
    return db.exec(statement).first()

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password"""
    user = get_user(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_session)
) -> User:
    """Get the current authenticated user from the token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
        
    user = get_user(db, email=token_data.email)
    if user is None:
        raise credentials_exception
        
    return user

# Function to decode Google JWT token to create our own JWT
def create_token_from_google_user(user_info: dict) -> str:
    """Create JWT token from Google user data"""
    data = {
        "sub": user_info.get("email"),
        "name": user_info.get("name"),
        "picture": user_info.get("picture")
    }
    return create_access_token(data)

# Permission utilities
def get_user_permissions(db: Session, user: User) -> List[str]:
    """Get all permissions for a user based on their roles"""
    if user.is_superuser:
        # Superuser has all permissions
        statement = select(Permission)
        permissions = db.exec(statement).all()
        return [p.name for p in permissions]
    
    # Query for UserRole to get roles
    statement = select(UserRole).where(UserRole.user_id == user.id)
    user_roles = db.exec(statement).all()
    role_ids = [ur.role_id for ur in user_roles]
    
    if not role_ids:
        return []
    
    # Query for RolePermission to get permissions
    statement = select(RolePermission).where(RolePermission.role_id.in_(role_ids))
    role_permissions = db.exec(statement).all()
    permission_ids = [rp.permission_id for rp in role_permissions]
    
    if not permission_ids:
        return []
    
    # Get actual permission names
    statement = select(Permission).where(Permission.id.in_(permission_ids))
    permissions = db.exec(statement).all()
    
    return [p.name for p in permissions]

def user_has_permission(db: Session, user: User, permission_name: str) -> bool:
    """Check if a user has a specific permission"""
    if user.is_superuser:
        return True
    
    user_permissions = get_user_permissions(db, user)
    return permission_name in user_permissions

def require_permission(permission_name: str):
    """Dependency to require a specific permission"""
    def permission_dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_session)
    ):
        if not user_has_permission(db, current_user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name} required"
            )
        return current_user
    
    return permission_dependency 