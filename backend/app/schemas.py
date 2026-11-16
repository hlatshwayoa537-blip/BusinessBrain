from typing import Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]

class RegisterRequest(BaseModel):
    full_name: Name
    email: EmailStr
    password: Password
    business_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    industry: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    country: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$")] = "ZA"
    profile_image_data_url: str | None = Field(default=None, max_length=2_800_000)

    @field_validator("profile_image_data_url")
    @classmethod
    def validate_profile_image(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
        if not value.startswith(allowed):
            raise ValueError("Profile image must be a JPEG, PNG or WebP image.")
        return value

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str

class BusinessProfileUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)] | None = None
    industry: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)] | None = None
    country: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$")] | None = None
    registration_number: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=24)
    description: str | None = Field(default=None, max_length=2000)
    directory_listed: bool | None = None
    public_email: bool | None = None
    public_phone: bool | None = None
    public_website: bool | None = None
    public_location: bool | None = None
    profile_image_data_url: str | None = Field(default=None, max_length=2_800_000)

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Website must start with https:// or http://.")
        return value

    @field_validator("profile_image_data_url")
    @classmethod
    def validate_profile_image(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
        if not value.startswith(allowed):
            raise ValueError("Profile image must be a JPEG, PNG or WebP image.")
        return value

class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    industry: str
    country: str
    profile_image_data_url: str | None = None
    registration_number: str | None = None
    website: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    address_line: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    description: str | None = None
    directory_listed: bool = False
    public_email: bool = False
    public_phone: bool = False
    public_website: bool = False
    public_location: bool = False

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    business: BusinessResponse


class PublicBusinessResponse(BaseModel):
    id: str
    name: str
    industry: str
    country: str
    profile_image_data_url: str | None = None
    website: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    city: str | None = None
    province: str | None = None
    description: str | None = None
