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
    referral_code: str | None = Field(default=None, min_length=4, max_length=20)

    @field_validator("profile_image_data_url")
    @classmethod
    def validate_profile_image(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
        if not value.startswith(allowed):
            raise ValueError("Profile image must be a JPEG, PNG or WebP image.")
        return value

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: Annotated[str, StringConstraints(min_length=32, max_length=128)]
    new_password: Password


class LoginRequest(BaseModel):
    # Existing business owners may continue using email; staff can sign in with WhatsApp phone.
    identifier: str | None = Field(default=None, min_length=3, max_length=320)
    email: EmailStr | None = None
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


class ConversationInviteCreate(BaseModel):
    invited_business_id: str = Field(min_length=36, max_length=36)
    invitation_message: str | None = Field(default=None, max_length=1000)
    access_password: Annotated[str, StringConstraints(min_length=8, max_length=128)]

class InvitationDecision(BaseModel):
    access_password: Annotated[str, StringConstraints(min_length=8, max_length=128)]

class InvitationResponse(BaseModel):
    id: str
    host_business_id: str
    host_business_name: str
    invited_business_id: str
    invited_business_name: str
    invitation_message: str | None = None
    status: str
    expires_at: object
    created_at: object

class ConversationMessageCreate(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]

class ConversationMessageResponse(BaseModel):
    id: str
    sender_business_id: str
    sender_business_name: str
    sender_user_name: str
    body: str
    created_at: object

class ConversationResponse(BaseModel):
    id: str
    host_business_id: str
    host_business_name: str
    invited_business_id: str
    invited_business_name: str
    status: str
    created_at: object
    deal_room_id: str | None = None
    deal_room_status: str | None = None

class DealRoomStatusUpdate(BaseModel):
    status: Annotated[str, StringConstraints(pattern=r"^(discussion|negotiation|proposal_submitted|agreement_reached|deal_completed|deal_cancelled)$")]

class DealRoomResponse(BaseModel):
    id: str
    conversation_id: str
    status: str
    created_at: object
    updated_at: object

class DealRoomMessageResponse(BaseModel):
    id: str
    sender_business_id: str
    sender_business_name: str
    sender_user_name: str
    body: str
    created_at: object


class JobCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=180)]
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=180)
    employment_type: Annotated[str, StringConstraints(pattern=r"^(full_time|part_time|contract|internship|temporary)$")] = "full_time"
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=30, max_length=12000)]
    requirements: str | None = Field(default=None, max_length=8000)
    status: Annotated[str, StringConstraints(pattern=r"^(draft|published|closed)$")] = "draft"

class JobApplicationCreate(BaseModel):
    applicant_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=180)
    experience: str | None = Field(default=None, max_length=80)
    resume_url: str | None = Field(default=None, max_length=500)
    cover_letter: str | None = Field(default=None, max_length=5000)

class JobStatusUpdate(BaseModel):
    status: Annotated[str, StringConstraints(pattern=r"^(draft|published|closed)$")]

class ApplicationStatusUpdate(BaseModel):
    status: Annotated[str, StringConstraints(pattern=r"^(new|reviewing|shortlisted|interview|rejected|hired)$")]


class PublicJobApplicationCreate(JobApplicationCreate):
    consent_to_share: bool
    website: str = Field(default="", max_length=200)

    @field_validator("consent_to_share")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Please consent to sharing your application with the hiring business.")
        return value

    @field_validator("resume_url")
    @classmethod
    def validate_resume_url(cls, value: str | None) -> str | None:
        if value and not value.startswith("https://"):
            raise ValueError("CV links must use a secure https:// address.")
        return value
