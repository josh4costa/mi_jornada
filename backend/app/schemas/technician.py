from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr
from app.schemas.user import UserResponse

class TechnicianBase(BaseModel):
    employee_number: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True

class TechnicianCreate(TechnicianBase):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=72)

class TechnicianResponse(TechnicianBase):
    id: UUID
    user_id: UUID
    user: UserResponse
    model_config = {"from_attributes": True}
