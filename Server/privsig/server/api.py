import asyncio
import hashlib
import json
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update, delete

from privsig.catalog import RESOURCES, ROLES, APPS
from .db import make_db, now, uid, School, SchoolClass, User, Student, Session, Record, Revision, Notification, Audit, AuditHead
from .policy import permits, allowed_apps, object_allowed, visible_students, LEAD, TEACH
from .validation import validate_data, validate_user_scopes, bad

hasher=PasswordHasher(time_cost=2,memory_cost=65536,parallelism=2)
bearer=HTTPBearer(auto_error=False)

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Login(Strict):
    username: str=Field(min_length=1,max_length=80)
    password: str=Field(min_length=1,max_length=200)

class Payload(Strict):
    data: dict

class EditPayload(Payload):
    version: int=Field(ge=1)

class DeletePayload(Strict):
    version: int=Field(ge=1)

class UserPayload(Strict):
    username: str=Field(min_length=3,max_length=80,pattern=r'^[a-zA-Z0-9_.-]+$')
    name: str=Field(min_length=1,max_length=120)
    role: str
    password: str=Field(min_length=12,max_length=128)
    school_id: str|None=None
    class_ids: list[str]=[]
    student_ids: list[str]=[]
    disabled_apps: list[str]=[]

class UserEdit(Strict):
    name: str=Field(min_length=1,max_length=120)
    role: str
    active: bool=True
    password: str|None=Field(default=None,min_length=12,max_length=128)
    class_ids: list[str]=[]
    student_ids: list[str]=[]
    disabled_apps: list[str]=[]

class Named(Strict):
    name: str=Field(min_length=1,max_length=160)

class StudentPayload(Named):
    class_id: str

class PasswordChange(Strict):
    old_password: str
    new_password: str=Field(min_length=12,max_length=128)

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def public_user(u):
    return {'id':u.id,'name':u.name,'username':u.username,'role':u.role,'school_id':u.school_id,
            'active':u.active,'class_ids':u.class_ids,'student_ids':u.student_ids,'disabled_apps':u.disabled_apps}

def serialize(r):
    return {'id':r.id,'module':r.module,'author_id':r.author_id,'data':r.data,'version':r.version,'created_at':r.created_at,'updated_at':r.updated_at}

def audit(db,u,action,object_id):
    head=db.get(AuditHead,1)
    at=now()
    payload=json.dumps([u.school_id,u.id,action,object_id,at,head.value],ensure_ascii=False,separators=(',',':'))
    value=hashlib.sha256(payload.encode()).hexdigest()
    db.add(Audit(school_id=u.school_id,actor_id=u.id,action=action,object_id=object_id,at=at,prev_hash=head.value,hash=value))
    head.value=value

class Hub:
    def __init__(self, factory):
        self.factory=factory
        self.connections={}

    async def send_change(self, school_id, module, data, author_id, old_data=None):
        # No grade, message, name or case content goes into push envelopes.
        for ws,(user_id,token_hash) in list(self.connections.items()):
            with self.factory() as db:
                u=db.get(User,user_id); session=db.get(Session,token_hash)
                valid=u and u.active and session and session.expires>now()
                if not valid:
                    self.connections.pop(ws,None)
                    try: await ws.close(code=4401)
                    except Exception: pass
                    continue
                visible=u.school_id==school_id and (object_allowed(u,module,data,author_id) or (old_data and object_allowed(u,module,old_data,author_id)))
            if visible:
                try: await ws.send_json({'type':'changed','module':module})
                except Exception: self.connections.pop(ws,None)

    async def revoke(self, user_id):
        for ws,(candidate,_) in list(self.connections.items()):
            if candidate==user_id:
                self.connections.pop(ws,None)
                try: await ws.close(code=4401)
                except Exception: pass

def create_app(database_url='sqlite:///privsig-demo.db', demo=False):
    engine,factory=make_db(database_url)
    if demo:
        from .seed import seed_demo
        seed_demo(factory)

    @asynccontextmanager
    async def lifespan(app):
        yield
        for ws in list(app.state.hub.connections):
            try: await ws.close(code=1001)
            except Exception: pass
        engine.dispose()

    app=FastAPI(title='PRIVSIG SCHOOL OS',version='0.1.0',lifespan=lifespan,docs_url='/docs' if demo else None,redoc_url=None)
    app.state.factory=factory
    app.state.engine=engine
    app.state.hub=Hub(factory)
    app.state.write_lock=threading.RLock()
    attempts=defaultdict(list)
    attempt_lock=threading.Lock()

    def database():
        with factory() as db: yield db

    def current(creds: HTTPAuthorizationCredentials|None=Depends(bearer),db=Depends(database)):
        if not creds: raise HTTPException(401,'Zaloguj się.',headers={'WWW-Authenticate':'Bearer'})
        session=db.get(Session,digest(creds.credentials))
        if not session or session.expires<=now(): raise HTTPException(401,'Sesja wygasła.')
        u=db.get(User,session.user_id)
        if not u or not u.active: raise HTTPException(401,'Konto jest nieaktywne.')
        return u

    def manage(u):
        if u.role not in LEAD or 'admin' not in allowed_apps(u): raise HTTPException(403,'Wymagane uprawnienia administracyjne.')

    def lock(db):
        # A common row serializes writes also on PostgreSQL; SQLite demo uses RLock.
        db.scalar(select(AuditHead).where(AuditHead.id==1).with_for_update())

    def record(db,u,module,rid,write=False):
        r=db.get(Record,rid)
        if not r or r.deleted or r.module!=module or r.school_id!=u.school_id or not object_allowed(u,module,r.data,r.author_id,write):
            raise HTTPException(404,'Nie znaleziono rekordu w zakresie uprawnień.')
        return r

    def notify(db,u,module,data):
        recipients=set()
        if module in {'grades','notes','attendance','finals'}:
            sid=data.get('student_id')
            for target in db.scalars(select(User).where(User.school_id==u.school_id,User.active.is_(True))):
                if target.role in {'student','parent'} and sid in target.student_ids and permits(target,module): recipients.add(target.id)
        if module=='messages': recipients.add(data['recipient_id'])
        if module in {'maintenance','school_tasks'}: recipients.add(data['assignee_id'])
        title={'grades':'Nowa lub zmieniona ocena','notes':'Nowa informacja wychowawcza','attendance':'Zaktualizowano frekwencję','finals':'Zaktualizowano ocenę końcową','messages':'Nowa wiadomość'}.get(module,'Zaktualizowano: '+RESOURCES[module][0])
        for recipient in recipients: db.add(Notification(user_id=recipient,module=module,title=title))

    @app.middleware('http')
    async def headers(request,call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.get('/health')
    def health(db=Depends(database)):
        db.scalar(select(AuditHead.id).limit(1))
        return {'status':'ok','version':'0.1.0','demo':demo,'database':engine.dialect.name}

    @app.post('/auth/login')
    def login(body:Login,request:Request,db=Depends(database)):
        key=(request.client.host if request.client else '?',body.username.lower())
        t=time.monotonic()
        with attempt_lock:
            attempts[key]=[x for x in attempts[key] if t-x<300]
            if len(attempts[key])>=10: raise HTTPException(429,'Zbyt wiele prób. Spróbuj za pięć minut.')
            attempts[key].append(t)
            if len(attempts)>10000:
                for old in list(attempts):
                    if not attempts[old] or t-attempts[old][-1]>300: del attempts[old]
        u=db.scalar(select(User).where(User.username==body.username))
        valid=False
        if u and u.active:
            try: valid=hasher.verify(u.password_hash,body.password)
            except (VerifyMismatchError,InvalidHashError): pass
        else:
            # Similar password-hash cost for unknown and disabled users.
            hasher.hash(body.password)
        if not valid: raise HTTPException(401,'Nieprawidłowy login lub hasło.')
        with attempt_lock: attempts.pop(key,None)
        token=secrets.token_urlsafe(48)
        with app.state.write_lock:
            lock(db)
            db.execute(delete(Session).where(Session.expires<=now()))
            db.add(Session(token_hash=digest(token),user_id=u.id,expires=(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()))
            audit(db,u,'login',u.id); db.commit()
        return {'token':token,'user':public_user(u),'apps':allowed_apps(u)}

    @app.post('/auth/logout')
    async def logout(creds:HTTPAuthorizationCredentials=Depends(bearer),u=Depends(current),db=Depends(database)):
        with app.state.write_lock:
            lock(db); db.execute(delete(Session).where(Session.token_hash==digest(creds.credentials)))
            audit(db,u,'logout',u.id); db.commit()
        for ws,(_,tok) in list(app.state.hub.connections.items()):
            if tok==digest(creds.credentials):
                app.state.hub.connections.pop(ws,None)
                try: await ws.close(code=4401)
                except Exception: pass
        return {'ok':True}

    @app.post('/auth/password')
    async def change_password(body:PasswordChange,u=Depends(current),db=Depends(database)):
        try: hasher.verify(u.password_hash,body.old_password)
        except (VerifyMismatchError,InvalidHashError): raise HTTPException(403,'Błędne obecne hasło.')
        with app.state.write_lock:
            lock(db); u.password_hash=hasher.hash(body.new_password)
            db.execute(delete(Session).where(Session.user_id==u.id)); audit(db,u,'password-change',u.id); db.commit()
        await app.state.hub.revoke(u.id)
        return {'ok':True,'reauthenticate':True}

    @app.get('/me')
    def me(u=Depends(current),db=Depends(database)):
        school=db.get(School,u.school_id)
        return {'user':public_user(u),'school':school.name,'apps':allowed_apps(u),
                'permissions':{m:{'read':permits(u,m),'write':permits(u,m,True)} for m in RESOURCES}}

    @app.get('/directory')
    def directory(u=Depends(current),db=Depends(database)):
        # Contact list does not expose usernames, links or student data.
        return [{'id':x.id,'name':x.name,'role':x.role} for x in db.scalars(select(User).where(User.school_id==u.school_id,User.active.is_(True)).order_by(User.name))]

    @app.get('/roster')
    def roster(u=Depends(current),db=Depends(database)):
        students=visible_students(u,list(db.scalars(select(Student).where(Student.school_id==u.school_id))))
        classes=list(db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id)))
        if u.role not in LEAD|{'office','librarian'}: classes=[c for c in classes if c.id in u.class_ids]
        return {'students':[{'id':s.id,'name':s.name,'class_id':s.class_id} for s in students],
                'classes':[{'id':c.id,'name':c.name} for c in classes]}

    @app.get('/records/{module}')
    def list_records(module:str,u=Depends(current),db=Depends(database)):
        if not permits(u,module): raise HTTPException(403,'Brak dostępu do tej aplikacji.')
        rows=db.scalars(select(Record).where(Record.school_id==u.school_id,Record.module==module,Record.deleted.is_(False)).order_by(Record.created_at.desc()))
        visible=[r for r in rows if object_allowed(u,module,r.data,r.author_id)]
        if module=='cases':
            with app.state.write_lock:
                lock(db)
                for r in visible: audit(db,u,'read:cases',r.id)
                db.commit()
        return [serialize(r) for r in visible]

    @app.post('/records/{module}',status_code=201)
    async def create_record(module:str,body:Payload,u=Depends(current),db=Depends(database)):
        if not permits(u,module,True): raise HTTPException(403,'Brak prawa zapisu.')
        with app.state.write_lock:
            lock(db)
            data=validate_data(module,body.data,db,u)
            if not object_allowed(u,module,data,u.id,True): raise HTTPException(403,'Rekord jest poza zakresem uprawnień.')
            r=Record(id=uid(),school_id=u.school_id,module=module,author_id=u.id,data=data,version=1,created_at=now(),updated_at=now())
            db.add(r); db.flush()
            db.add(Revision(record_id=r.id,actor_id=u.id,version=1,data=data))
            notify(db,u,module,data); audit(db,u,'create:'+module,r.id); db.commit()
        await app.state.hub.send_change(u.school_id,module,r.data,r.author_id)
        return serialize(r)

    @app.put('/records/{module}/{rid}')
    async def edit_record(module:str,rid:str,body:EditPayload,u=Depends(current),db=Depends(database)):
        if not permits(u,module,True): raise HTTPException(403,'Brak prawa zapisu.')
        with app.state.write_lock:
            lock(db)
            r=record(db,u,module,rid,True)
            if r.version!=body.version: raise HTTPException(409,'Rekord zmienił się na innym komputerze. Odśwież widok.')
            old=dict(r.data); data=validate_data(module,body.data,db,u,r)
            if not object_allowed(u,module,data,r.author_id,True): raise HTTPException(403,'Nowe dane są poza zakresem uprawnień.')
            r.data=data; r.version+=1; r.updated_at=now()
            db.add(Revision(record_id=r.id,actor_id=u.id,version=r.version,data=data))
            notify(db,u,module,data); audit(db,u,'edit:'+module,r.id); db.commit()
        await app.state.hub.send_change(u.school_id,module,data,r.author_id,old)
        return serialize(r)

    @app.delete('/records/{module}/{rid}')
    async def remove_record(module:str,rid:str,body:DeletePayload,u=Depends(current),db=Depends(database)):
        if not permits(u,module,True): raise HTTPException(403,'Brak prawa usuwania.')
        with app.state.write_lock:
            lock(db)
            r=record(db,u,module,rid,True)
            if r.version!=body.version: raise HTTPException(409,'Odśwież rekord przed usunięciem.')
            if module=='books':
                for loan in db.scalars(select(Record).where(Record.school_id==u.school_id,Record.module=='loans',Record.deleted.is_(False))):
                    if loan.data['book_id']==rid and loan.data['status']=='Wypożyczona': raise HTTPException(409,'Książka ma aktywne wypożyczenia.')
            r.deleted=True; r.version+=1; r.updated_at=now()
            db.add(Revision(record_id=r.id,actor_id=u.id,version=r.version,data={'deleted':True}))
            audit(db,u,'delete:'+module,rid); db.commit()
        await app.state.hub.send_change(u.school_id,module,r.data,r.author_id)
        return {'ok':True}

    @app.get('/records/{module}/{rid}/history')
    def history(module:str,rid:str,u=Depends(current),db=Depends(database)):
        if u.role not in TEACH and module in {'grades','attendance','notes','finals'}: raise HTTPException(403,'Historia zmian jest dostępna dla pracowników uprawnionych do dziennika.')
        r=record(db,u,module,rid)
        # Historical snapshots can contain data under a former access scope.
        revisions=db.scalars(select(Revision).where(Revision.record_id==r.id).order_by(Revision.version))
        result=[{'version':v.version,'at':v.at,'actor_id':v.actor_id,'data':v.data} for v in revisions if v.data.get('deleted') or object_allowed(u,module,v.data,r.author_id)]
        if module=='cases':
            with app.state.write_lock: lock(db); audit(db,u,'history:cases',r.id); db.commit()
        return result

    @app.get('/notifications')
    def notifications(u=Depends(current),db=Depends(database)):
        return [{'id':n.id,'title':n.title,'module':n.module,'read':n.read,'at':n.at} for n in db.scalars(select(Notification).where(Notification.user_id==u.id).order_by(Notification.at.desc()).limit(200))]

    @app.post('/notifications/read')
    def read_notifications(u=Depends(current),db=Depends(database)):
        db.execute(update(Notification).where(Notification.user_id==u.id).values(read=True)); db.commit()
        return {'ok':True}

    @app.get('/reports')
    def reports(u=Depends(current),db=Depends(database)):
        if 'reports' not in allowed_apps(u): raise HTTPException(403,'Brak dostępu do raportów.')
        students=visible_students(u,list(db.scalars(select(Student).where(Student.school_id==u.school_id))))
        rows=list(db.scalars(select(Record).where(Record.school_id==u.school_id,Record.module.in_(['grades','attendance']),Record.deleted.is_(False))))
        rows=[r for r in rows if object_allowed(u,r.module,r.data,r.author_id)]
        result=[]
        for s in students:
            grades=[r.data for r in rows if r.module=='grades' and r.data['student_id']==s.id]
            attendance=[r.data for r in rows if r.module=='attendance' and r.data['student_id']==s.id]
            subjects=sorted({g['subject'] for g in grades}) or ['—']
            for subject in subjects:
                values=[g for g in grades if g['subject']==subject]
                weight=sum(g['weight'] for g in values)
                average=round(sum(min(6,max(1,g['value']+({'+':0.5,'-':-0.25}.get(g['modifier'],0))))*g['weight'] for g in values)/weight,2) if weight else None
                present=sum(a['status'] in {'Obecny','Spóźnienie'} for a in attendance)
                result.append({'student':s.name,'subject':subject,'average':average,'grade_count':len(values),
                               'attendance_pct':round(present/len(attendance)*100,1) if attendance else None,'lessons':len(attendance)})
        return result

    @app.get('/admin/users')
    def users(u=Depends(current),db=Depends(database)):
        manage(u)
        return [public_user(x) for x in db.scalars(select(User).where(User.school_id==u.school_id).order_by(User.name))]

    @app.post('/admin/users',status_code=201)
    async def create_user(body:UserPayload,u=Depends(current),db=Depends(database)):
        manage(u)
        sid=body.school_id or u.school_id
        if sid!=u.school_id and u.role!='superadmin': raise HTTPException(403,'Inna szkoła.')
        if not db.get(School,sid): bad('Nieznana szkoła.')
        if body.role=='superadmin' and u.role!='superadmin': raise HTTPException(403,'Nie możesz nadawać tej roli.')
        validate_user_scopes(db,sid,body.class_ids,body.student_ids,body.disabled_apps,body.role)
        with app.state.write_lock:
            lock(db)
            if db.scalar(select(User).where(User.username==body.username)): raise HTTPException(409,'Login jest zajęty.')
            obj=User(id=uid(),school_id=sid,username=body.username,name=body.name,role=body.role,password_hash=hasher.hash(body.password),class_ids=body.class_ids,student_ids=body.student_ids,disabled_apps=body.disabled_apps,active=True)
            db.add(obj); audit(db,u,'user-create',obj.id); db.commit()
        return public_user(obj)

    @app.put('/admin/users/{user_id}')
    async def edit_user(user_id:str,body:UserEdit,u=Depends(current),db=Depends(database)):
        manage(u)
        target=db.get(User,user_id)
        if not target or (target.school_id!=u.school_id and u.role!='superadmin'): raise HTTPException(404,'Nie znaleziono konta.')
        if (target.role=='superadmin' or body.role=='superadmin') and u.role!='superadmin': raise HTTPException(403,'Konto superadministratora jest chronione.')
        if target.id==u.id and (not body.active or body.role!=u.role or 'admin' in body.disabled_apps): raise HTTPException(409,'Nie możesz odebrać sobie dostępu administracyjnego.')
        validate_user_scopes(db,target.school_id,body.class_ids,body.student_ids,body.disabled_apps,body.role)
        with app.state.write_lock:
            lock(db)
            for key in ('name','role','active','class_ids','student_ids','disabled_apps'): setattr(target,key,getattr(body,key))
            if body.password: target.password_hash=hasher.hash(body.password)
            db.execute(delete(Session).where(Session.user_id==target.id)); audit(db,u,'user-edit',target.id); db.commit()
        await app.state.hub.revoke(target.id)
        return public_user(target)

    @app.get('/admin/schools')
    def schools(u=Depends(current),db=Depends(database)):
        manage(u)
        q=select(School)
        if u.role!='superadmin': q=q.where(School.id==u.school_id)
        return [{'id':s.id,'name':s.name} for s in db.scalars(q)]

    @app.post('/admin/schools',status_code=201)
    def add_school(body:Named,u=Depends(current),db=Depends(database)):
        if u.role!='superadmin' or 'admin' not in allowed_apps(u): raise HTTPException(403,'Tylko superadministrator tworzy szkoły.')
        with app.state.write_lock:
            lock(db); s=School(id=uid(),name=body.name); db.add(s); audit(db,u,'school-create',s.id); db.commit()
        return {'id':s.id,'name':s.name}

    @app.post('/admin/switch-school/{school_id}')
    async def switch_school(school_id:str,u=Depends(current),db=Depends(database)):
        if u.role!='superadmin' or 'admin' not in allowed_apps(u): raise HTTPException(403,'Tylko superadministrator przełącza szkołę.')
        if not db.get(School,school_id): raise HTTPException(404,'Brak szkoły.')
        with app.state.write_lock:
            lock(db); audit(db,u,'school-switch',school_id); u.school_id=school_id
            u.class_ids=[]; u.student_ids=[]; db.execute(delete(Session).where(Session.user_id==u.id)); db.commit()
        await app.state.hub.revoke(u.id)
        return {'ok':True,'reauthenticate':True}

    @app.post('/admin/classes',status_code=201)
    def add_class(body:Named,u=Depends(current),db=Depends(database)):
        manage(u)
        with app.state.write_lock:
            lock(db); c=SchoolClass(id=uid(),school_id=u.school_id,name=body.name); db.add(c); audit(db,u,'class-create',c.id); db.commit()
        return {'id':c.id,'name':c.name}

    @app.post('/admin/students',status_code=201)
    def add_student(body:StudentPayload,u=Depends(current),db=Depends(database)):
        manage(u)
        cls=db.get(SchoolClass,body.class_id)
        if not cls or cls.school_id!=u.school_id: bad('Nieprawidłowa klasa.')
        with app.state.write_lock:
            lock(db); s=Student(id=uid(),school_id=u.school_id,class_id=cls.id,name=body.name); db.add(s); audit(db,u,'student-create',s.id); db.commit()
        return {'id':s.id,'name':s.name,'class_id':s.class_id}

    @app.get('/admin/audit')
    def audit_list(u=Depends(current),db=Depends(database)):
        manage(u)
        rows=db.scalars(select(Audit).where(Audit.school_id==u.school_id).order_by(Audit.id.desc()).limit(500))
        return [{'id':a.id,'actor_id':a.actor_id,'action':a.action,'object_id':a.object_id,'at':a.at,'hash':a.hash} for a in rows]

    @app.get('/admin/audit/verify')
    def verify_audit(u=Depends(current),db=Depends(database)):
        if u.role!='superadmin' or 'admin' not in allowed_apps(u): raise HTTPException(403,'Tylko superadministrator weryfikuje globalny audyt.')
        prev='0'*64; count=0
        for a in db.scalars(select(Audit).order_by(Audit.id)):
            payload=json.dumps([a.school_id,a.actor_id,a.action,a.object_id,a.at,a.prev_hash],ensure_ascii=False,separators=(',',':'))
            if a.prev_hash!=prev or hashlib.sha256(payload.encode()).hexdigest()!=a.hash: return {'valid':False,'checked':count}
            prev=a.hash; count+=1
        return {'valid':prev==db.get(AuditHead,1).value,'checked':count}

    @app.websocket('/ws')
    async def websocket(ws:WebSocket):
        header=ws.headers.get('authorization','')
        if not header.startswith('Bearer '): await ws.close(code=4401); return
        token_hash=digest(header[7:])
        with factory() as db:
            s=db.get(Session,token_hash); u=db.get(User,s.user_id) if s else None
            if not s or s.expires<=now() or not u or not u.active: await ws.close(code=4401); return
            user_id=u.id
        await ws.accept(); app.state.hub.connections[ws]=(user_id,token_hash)
        try:
            while True:
                # Check revocation and expiry even while no school records change.
                try: message=await asyncio.wait_for(ws.receive_text(),timeout=25)
                except asyncio.TimeoutError: message='ping'
                with factory() as db:
                    s=db.get(Session,token_hash); u=db.get(User,user_id)
                    if not s or s.expires<=now() or not u or not u.active: await ws.close(code=4401); break
                if message=='ping': await ws.send_json({'type':'pong'})
                elif len(message)>1000: await ws.close(code=1009); break
        except (WebSocketDisconnect,RuntimeError): pass
        finally: app.state.hub.connections.pop(ws,None)

    return app
