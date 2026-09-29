import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base
def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__="users"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    username:Mapped[str]=mapped_column(String(40),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    display_name:Mapped[str]=mapped_column(String(60))
    is_admin:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Room(Base):
    __tablename__="rooms"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name:Mapped[str]=mapped_column(String(60))
    owner_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Membership(Base):
    __tablename__="memberships"; __table_args__=(UniqueConstraint("room_id","user_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    room_id:Mapped[str]=mapped_column(ForeignKey("rooms.id",ondelete="CASCADE"),index=True)
    user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    role:Mapped[str]=mapped_column(String(12),default="member")
    joined_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Invite(Base):
    __tablename__="invites"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    room_id:Mapped[str]=mapped_column(ForeignKey("rooms.id",ondelete="CASCADE"),index=True)
    code_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    max_uses:Mapped[int]=mapped_column(default=10)
    use_count:Mapped[int]=mapped_column(default=0)
    revoked:Mapped[bool]=mapped_column(Boolean,default=False)
class Message(Base):
    __tablename__="messages"
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    room_id:Mapped[str]=mapped_column(ForeignKey("rooms.id",ondelete="CASCADE"),index=True)
    user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    device_id:Mapped[str]=mapped_column(String(64),index=True)
    device_name:Mapped[str]=mapped_column(String(60))
    content:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
Index("ix_messages_room_created",Message.room_id,Message.created_at.desc())

class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    actor_id:Mapped[str|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    actor_name:Mapped[str]=mapped_column(String(60),default="system")
    action:Mapped[str]=mapped_column(String(80),index=True)
    target_type:Mapped[str|None]=mapped_column(String(40),nullable=True)
    target_id:Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    detail:Mapped[str|None]=mapped_column(Text,nullable=True)
    ip_address:Mapped[str|None]=mapped_column(String(64),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
Index("ix_audit_created_action",AuditLog.created_at.desc(),AuditLog.action)
