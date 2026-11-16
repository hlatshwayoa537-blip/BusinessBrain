from typing import Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]

class RegisterRequest(BaseModel):
    full_name: Name
    email: EmailStr
    password: Password
    business_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    industry: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    country: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$")] = "ZA"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str

class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    industry: str
    country: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    business: BusinessResponse
