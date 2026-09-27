from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username_or_email: str
    password: str
    remember_me: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
