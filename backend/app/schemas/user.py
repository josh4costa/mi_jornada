from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    role: UserRole
    is_active: bool = True

class TechnicianFields(BaseModel):
    reminders_enabled: bool = False
    employee_number: Optional[str] = Field(default=None, max_length=30)
    phone: Optional[str] = Field(default=None, max_length=20)

class TechnicianSummary(TechnicianFields):
    id: UUID
    model_config = {"from_attributes": True}

class UserCreate(UserBase, TechnicianFields):
    password: str = Field(min_length=8, max_length=72)

class UserUpdate(TechnicianFields):
    username: Optional[str] = Field(default=None, min_length=1, max_length=50)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)

class UserResponse(UserBase):
    must_change_password: bool = False
    # Existing records may use legacy internal domains; validate email on input only.
    email: str
    technician: Optional[TechnicianSummary] = None
    id: UUID
    model_config = {"from_attributes": True}

class UserStatusUpdate(BaseModel):
    is_active: bool = Field(default=False, strict=True)
