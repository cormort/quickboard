from pathlib import Path
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, delete, func, text, inspect
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from .config import settings
from .db import Base,engine,db_session
from .models import User,Room,Membership,Invite,Message,AuditLog
from .schemas import RegisterIn,LoginIn,RoomIn,JoinIn,InviteIn,MessageIn
from .security import hash_password,verify_password,make_token,current_user,invite_code,code_hash
Base.metadata.create_all(engine)

def migrate_and_bootstrap():
    # create_all 不會替既有 SQLite 表格新增欄位，啟動時執行安全的輕量遷移。
    with engine.begin() as c:
        cols={x[1] for x in c.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
        if "is_admin" not in cols: c.exec_driver_sql("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
        if "is_active" not in cols: c.exec_driver_sql("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
        c.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_users_is_admin ON users(is_admin)")
        c.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_users_is_active ON users(is_active)")
    with next(db_session()) as db:
        admin=db.scalar(select(User).where(User.username==settings.bootstrap_admin_username.lower()))
        if not admin:
            if len(settings.bootstrap_admin_password)<12:
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD 必須至少 12 字元")
            admin=User(username=settings.bootstrap_admin_username.lower(),display_name="系統管理員",password_hash=hash_password(settings.bootstrap_admin_password),is_admin=True,is_active=True)
            db.add(admin); db.commit()
        elif not admin.is_admin:
            admin.is_admin=True; admin.is_active=True; db.commit()
        if settings.auto_cleanup_enabled and settings.message_retention_days>0:
            cutoff=datetime.now(timezone.utc)-timedelta(days=settings.message_retention_days)
            db.execute(delete(Message).where(Message.created_at < cutoff)); db.commit()

migrate_and_bootstrap()
app=FastAPI(title="QuickBoard Self-hosted",docs_url=None,redoc_url=None)
limiter=Limiter(key_func=get_remote_address,default_limits=["120/minute"])
app.state.limiter=limiter; app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler)
if settings.cors_origins:
    app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',')],allow_credentials=True,allow_methods=["GET","POST","DELETE"],allow_headers=["Content-Type"])
STATIC=Path(__file__).parent/'static'
app.mount('/static',StaticFiles(directory=STATIC),name='static')
def me(request:Request,db:Session=Depends(db_session)): return current_user(request,db)
def audit(db:Session,request:Request|None,actor:User|None,action:str,target_type:str|None=None,target_id:str|None=None,detail:str|None=None):
    ip=request.client.host if request and request.client else None
    db.add(AuditLog(actor_id=actor.id if actor else None,actor_name=actor.display_name if actor else "system",action=action,target_type=target_type,target_id=target_id,detail=detail,ip_address=ip))

def membership(db,user_id,room_id):
    m=db.scalar(select(Membership).where(Membership.user_id==user_id,Membership.room_id==room_id))
    if not m: raise HTTPException(403,"不是房間成員")
    return m
@app.get('/api/health')
def health(): return {'ok':True}
@app.post('/api/auth/register')
@limiter.limit("5/minute")
def register(request:Request,data:RegisterIn,response:Response,db:Session=Depends(db_session)):
    if db.scalar(select(User).where(User.username==data.username.lower())): raise HTTPException(409,"帳號已存在")
    inv=db.scalar(select(Invite).where(Invite.code_hash==code_hash(data.invite_code)))
    current=datetime.now(timezone.utc)
    if not inv or inv.revoked or inv.expires_at<current or inv.use_count>=inv.max_uses: raise HTTPException(400,"邀請碼無效、已過期或已達使用上限")
    u=User(username=data.username.lower(),password_hash=hash_password(data.password),display_name=data.display_name.strip(),is_active=True)
    db.add(u);db.flush();db.add(Membership(room_id=inv.room_id,user_id=u.id,role='member'));inv.use_count+=1;db.commit()
    response.set_cookie('qb_session',make_token(u.id),httponly=True,secure=settings.cookie_secure,samesite='strict',max_age=settings.access_token_minutes*60,path='/')
    return {'ok':True}
@app.post('/api/auth/login')
@limiter.limit("10/minute")
def login(request:Request,data:LoginIn,response:Response,db:Session=Depends(db_session)):
    u=db.scalar(select(User).where(User.username==data.username.lower()))
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,"帳號或密碼錯誤")
    response.set_cookie('qb_session',make_token(u.id),httponly=True,secure=settings.cookie_secure,samesite='strict',max_age=settings.access_token_minutes*60,path='/')
    return {'id':u.id,'display_name':u.display_name}
@app.post('/api/auth/logout')
def logout(response:Response): response.delete_cookie('qb_session',path='/');return {'ok':True}
@app.get('/api/me')
def get_me(user=Depends(me)): return {'id':user.id,'username':user.username,'display_name':user.display_name,'is_admin':user.is_admin,'is_active':user.is_active}
@app.get('/api/rooms')
def rooms(user=Depends(me),db:Session=Depends(db_session)):
    q=select(Room,Membership.role).join(Membership,Membership.room_id==Room.id).where(Membership.user_id==user.id).order_by(Room.created_at.desc())
    return [{'id':r.id,'name':r.name,'role':role} for r,role in db.execute(q)]
@app.post('/api/rooms')
@limiter.limit("10/hour")
def create_room(request:Request,data:RoomIn,user=Depends(me),db:Session=Depends(db_session)):
    r=Room(name=data.name.strip(),owner_id=user.id);db.add(r);db.flush();db.add(Membership(room_id=r.id,user_id=user.id,role='owner'));db.commit();return {'id':r.id,'name':r.name,'role':'owner'}
@app.post('/api/rooms/join')
@limiter.limit("20/hour")
def join(request:Request,data:JoinIn,user=Depends(me),db:Session=Depends(db_session)):
    inv=db.scalar(select(Invite).where(Invite.code_hash==code_hash(data.code)).with_for_update())
    now=datetime.now(timezone.utc)
    if not inv or inv.revoked or inv.use_count>=inv.max_uses or inv.expires_at.replace(tzinfo=timezone.utc)<=now: raise HTTPException(400,"邀請碼無效或過期")
    exists=db.scalar(select(Membership).where(Membership.room_id==inv.room_id,Membership.user_id==user.id))
    if not exists: db.add(Membership(room_id=inv.room_id,user_id=user.id));inv.use_count+=1
    db.commit();r=db.get(Room,inv.room_id);return {'id':r.id,'name':r.name,'role':'member'}
@app.post('/api/rooms/{room_id}/invites')
@limiter.limit("20/hour")
def make_invite(request:Request,room_id:str,data:InviteIn,user=Depends(me),db:Session=Depends(db_session)):
    m=membership(db,user.id,room_id)
    if m.role!='owner': raise HTTPException(403,"只有房主可建立邀請碼")
    code=invite_code();inv=Invite(room_id=room_id,code_hash=code_hash(code),created_by=user.id,expires_at=datetime.now(timezone.utc)+timedelta(hours=data.expire_hours),max_uses=data.max_uses);db.add(inv);db.commit()
    return {'code':code,'expires_at':inv.expires_at,'max_uses':inv.max_uses}
@app.get('/api/rooms/{room_id}/messages')
def messages(room_id:str,limit:int=100,user=Depends(me),db:Session=Depends(db_session)):
    membership(db,user.id,room_id);limit=max(1,min(limit,200));q=select(Message,User.display_name).join(User,User.id==Message.user_id).where(Message.room_id==room_id).order_by(Message.created_at.desc()).limit(limit)
    return [{'id':m.id,'content':m.content,'device_id':m.device_id,'device_name':m.device_name,'user_id':m.user_id,'user_name':name,'created_at':m.created_at} for m,name in db.execute(q)]
@app.post('/api/rooms/{room_id}/messages')
@limiter.limit("30/minute")
def post_message(request:Request,room_id:str,data:MessageIn,user=Depends(me),db:Session=Depends(db_session)):
    membership(db,user.id,room_id)
    if len(data.content)>settings.max_message_length: raise HTTPException(413,"訊息過長")
    old=db.get(Message,data.id)
    if old:
        if old.user_id==user.id and old.room_id==room_id:return {'id':old.id,'duplicate':True}
        raise HTTPException(409,"訊息 ID 衝突")
    m=Message(id=data.id,room_id=room_id,user_id=user.id,device_id=data.device_id,device_name=data.device_name.strip(),content=data.content);db.add(m);db.commit();return {'id':m.id}
@app.delete('/api/messages/{message_id}')
def remove_message(message_id:str,user=Depends(me),db:Session=Depends(db_session)):
    m=db.get(Message,message_id)
    if not m: raise HTTPException(404,"訊息不存在")
    role=membership(db,user.id,m.room_id).role
    if m.user_id!=user.id and role!='owner' and not user.is_admin: raise HTTPException(403,"無權刪除")
    db.delete(m);db.commit();return {'ok':True}
def require_admin(user=Depends(me)):
    if not user.is_admin: raise HTTPException(403,"需要管理員權限")
    return user

@app.get('/api/admin/stats')
def admin_stats(admin=Depends(require_admin),db:Session=Depends(db_session)):
    cutoff=datetime.now(timezone.utc)-timedelta(days=1)
    return {
      'users':db.scalar(select(func.count()).select_from(User)),
      'active_users':db.scalar(select(func.count()).select_from(User).where(User.is_active==True)),
      'rooms':db.scalar(select(func.count()).select_from(Room)),
      'messages':db.scalar(select(func.count()).select_from(Message)),
      'messages_24h':db.scalar(select(func.count()).select_from(Message).where(Message.created_at>=cutoff)),
      'retention_days':settings.message_retention_days
    }

@app.get('/api/admin/users')
def admin_users(admin=Depends(require_admin),db:Session=Depends(db_session)):
    q=select(User).order_by(User.created_at.desc()).limit(500)
    return [{'id':u.id,'username':u.username,'display_name':u.display_name,'is_admin':u.is_admin,'is_active':u.is_active,'created_at':u.created_at} for u in db.scalars(q)]

@app.post('/api/admin/users/{user_id}/toggle-active')
def admin_toggle_user(request:Request,user_id:str,admin=Depends(require_admin),db:Session=Depends(db_session)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"使用者不存在")
    if u.id==admin.id: raise HTTPException(400,"不能停用目前登入的管理員")
    u.is_active=not u.is_active; audit(db,request,admin,'user.toggle_active','user',u.id,f'is_active={u.is_active}'); db.commit(); return {'id':u.id,'is_active':u.is_active}

@app.get('/api/admin/rooms')
def admin_rooms(admin=Depends(require_admin),db:Session=Depends(db_session)):
    q=select(Room,User.display_name,func.count(Message.id)).join(User,User.id==Room.owner_id).outerjoin(Message,Message.room_id==Room.id).group_by(Room.id,User.display_name).order_by(Room.created_at.desc())
    return [{'id':r.id,'name':r.name,'owner_name':owner,'message_count':count,'created_at':r.created_at} for r,owner,count in db.execute(q)]

@app.delete('/api/admin/rooms/{room_id}')
def admin_delete_room(request:Request,room_id:str,admin=Depends(require_admin),db:Session=Depends(db_session)):
    r=db.get(Room,room_id)
    if not r: raise HTTPException(404,"房間不存在")
    name=r.name; db.delete(r); audit(db,request,admin,'room.delete','room',room_id,f'name={name}'); db.commit(); return {'ok':True}

@app.post('/api/admin/cleanup')
def admin_cleanup(request:Request,days:int=30,room_id:str|None=None,admin=Depends(require_admin),db:Session=Depends(db_session)):
    days=max(0,min(days,3650)); cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    q=delete(Message).where(Message.created_at < cutoff)
    if room_id: q=q.where(Message.room_id==room_id)
    result=db.execute(q); count=result.rowcount or 0; audit(db,request,admin,'messages.cleanup','room',room_id,f'days={days}; deleted={count}'); db.commit(); return {'deleted':count,'cutoff':cutoff,'room_id':room_id}

@app.post('/api/admin/cleanup-all')
def admin_cleanup_all(request:Request,room_id:str|None=None,admin=Depends(require_admin),db:Session=Depends(db_session)):
    q=delete(Message)
    if room_id: q=q.where(Message.room_id==room_id)
    result=db.execute(q); count=result.rowcount or 0; audit(db,request,admin,'messages.cleanup_all','room',room_id,f'deleted={count}'); db.commit(); return {'deleted':count,'room_id':room_id}

@app.post('/api/admin/cleanup-invites')
def admin_cleanup_invites(request:Request,admin=Depends(require_admin),db:Session=Depends(db_session)):
    q=delete(Invite).where((Invite.expires_at < datetime.now(timezone.utc)) | (Invite.revoked==True) | (Invite.use_count>=Invite.max_uses))
    result=db.execute(q); count=result.rowcount or 0; audit(db,request,admin,'invites.cleanup',detail=f'deleted={count}'); db.commit(); return {'deleted':count}

@app.get('/api/admin/audit')
def admin_audit(page:int=1,page_size:int=50,action:str|None=None,date_from:datetime|None=None,date_to:datetime|None=None,admin=Depends(require_admin),db:Session=Depends(db_session)):
    page=max(1,page); page_size=max(10,min(page_size,200)); conditions=[]
    if action: conditions.append(AuditLog.action==action)
    if date_from: conditions.append(AuditLog.created_at>=date_from)
    if date_to: conditions.append(AuditLog.created_at<=date_to)
    count_q=select(func.count()).select_from(AuditLog)
    data_q=select(AuditLog)
    for condition in conditions: count_q=count_q.where(condition); data_q=data_q.where(condition)
    total=db.scalar(count_q) or 0; rows=db.scalars(data_q.order_by(AuditLog.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[{'id':x.id,'actor_name':x.actor_name,'action':x.action,'target_type':x.target_type,'target_id':x.target_id,'detail':x.detail,'ip_address':x.ip_address,'created_at':x.created_at} for x in rows],'page':page,'page_size':page_size,'total':total,'pages':max(1,(total+page_size-1)//page_size)}

@app.get('/api/admin/audit.csv')
def admin_audit_csv(action:str|None=None,date_from:datetime|None=None,date_to:datetime|None=None,admin=Depends(require_admin),db:Session=Depends(db_session)):
    import csv,io
    q=select(AuditLog)
    if action: q=q.where(AuditLog.action==action)
    if date_from: q=q.where(AuditLog.created_at>=date_from)
    if date_to: q=q.where(AuditLog.created_at<=date_to)
    rows=db.scalars(q.order_by(AuditLog.created_at.desc()).limit(10000)).all(); out=io.StringIO(); w=csv.writer(out); w.writerow(['created_at','actor','action','target_type','target_id','detail','ip_address'])
    for x in rows:w.writerow([x.created_at,x.actor_name,x.action,x.target_type,x.target_id,x.detail,x.ip_address])
    from fastapi.responses import Response as CsvResponse
    return CsvResponse(out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=quickboard-audit.csv'})

@app.get('/')
def index(): return FileResponse(STATIC/'index.html')
@app.get('/{path:path}')
def spa(path:str):
    f=STATIC/path
    return FileResponse(f if f.is_file() else STATIC/'index.html')
