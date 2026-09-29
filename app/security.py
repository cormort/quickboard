import hashlib, secrets
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from .config import settings
from .models import User
passwords=PasswordHash.recommended()
def hash_password(v): return passwords.hash(v)
def verify_password(v,h): return passwords.verify(v,h)
def make_token(user_id):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":user_id,"iat":now,"exp":now+timedelta(minutes=settings.access_token_minutes),"type":"access"},settings.app_secret,algorithm="HS256")
def current_user(request:Request,db:Session):
    token=request.cookies.get("qb_session")
    if not token: raise HTTPException(401,"請先登入")
    try: payload=jwt.decode(token,settings.app_secret,algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401,"登入已失效")
    user=db.get(User,payload.get("sub"))
    if not user: raise HTTPException(401,"使用者不存在")
    if not user.is_active: raise HTTPException(401,"帳號已停用")
    return user
def invite_code(): return '-'.join([secrets.token_hex(2).upper() for _ in range(3)])
def code_hash(code): return hashlib.sha256((settings.app_secret+code.replace('-','').upper()).encode()).hexdigest()
