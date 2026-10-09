from datetime import datetime, timezone
import uuid
from sqlalchemy import create_engine, String, Integer, Text, JSON, Boolean, ForeignKey, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid.uuid4())

class Base(DeclarativeBase):
    pass

class School(Base):
    __tablename__ = 'schools'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))

class SchoolClass(Base):
    __tablename__ = 'classes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('schools.id'), index=True)
    name: Mapped[str] = mapped_column(String(40))

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('schools.id'), index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    class_ids: Mapped[list] = mapped_column(JSON, default=list)
    student_ids: Mapped[list] = mapped_column(JSON, default=list)
    disabled_apps: Mapped[list] = mapped_column(JSON, default=list)

class Student(Base):
    __tablename__ = 'students'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('schools.id'), index=True)
    class_id: Mapped[str] = mapped_column(ForeignKey('classes.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires: Mapped[str] = mapped_column(String(40))

class Record(Base):
    __tablename__ = 'records'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('schools.id'), index=True)
    module: Mapped[str] = mapped_column(String(40), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    data: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

class Revision(Base):
    __tablename__ = 'revisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    record_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    at: Mapped[str] = mapped_column(String(40), default=now)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(250))
    module: Mapped[str] = mapped_column(String(40))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[str] = mapped_column(String(40), default=now)

class AuditHead(Base):
    __tablename__ = 'audit_head'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(64))

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str] = mapped_column(String(120))
    at: Mapped[str] = mapped_column(String(40))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

def make_db(url):
    engine = create_engine(url, connect_args={'check_same_thread':False} if url.startswith('sqlite') else {}, pool_pre_ping=True)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def pragmas(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA journal_mode=WAL')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        if not db.get(AuditHead,1):
            db.add(AuditHead(id=1,value='0'*64))
    return engine, factory
