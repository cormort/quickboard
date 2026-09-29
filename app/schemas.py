from pydantic import BaseModel, Field, field_validator
class RegisterIn(BaseModel):
    username:str=Field(min_length=3,max_length=40,pattern=r"^[A-Za-z0-9_.-]+$")
    password:str=Field(min_length=12,max_length=128)
    display_name:str=Field(min_length=1,max_length=60)
    invite_code:str=Field(min_length=8,max_length=32)
class LoginIn(BaseModel): username:str; password:str
class RoomIn(BaseModel): name:str=Field(min_length=1,max_length=60)
class JoinIn(BaseModel): code:str=Field(min_length=8,max_length=32)
class InviteIn(BaseModel): max_uses:int=Field(default=10,ge=1,le=100); expire_hours:int=Field(default=24,ge=1,le=720)
class MessageIn(BaseModel):
    id:str=Field(min_length=36,max_length=36)
    content:str=Field(min_length=1,max_length=5000)
    device_id:str=Field(min_length=8,max_length=64)
    device_name:str=Field(min_length=1,max_length=60)
    @field_validator('content')
    @classmethod
    def clean(cls,v):
        v=v.strip()
        if not v: raise ValueError('訊息不可為空')
        return v
