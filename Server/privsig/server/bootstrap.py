"""One-time production administrator setup from local environment, no demo seed."""
import os
from sqlalchemy import select
from .db import make_db, User, School, uid
from .api import hasher

def main():
    url=os.environ['DATABASE_URL']; password=os.environ['PRIVSIG_ADMIN_PASSWORD']
    if not url.startswith('postgresql') or len(password)<12:
        raise SystemExit('Wymagany PostgreSQL i hasło co najmniej 12 znaków.')
    engine,factory=make_db(url)
    with factory.begin() as db:
        if db.scalar(select(User).limit(1)): raise SystemExit('Konta już istnieją; konfiguracja początkowa przerwana.')
        s=School(id=uid(),name=os.getenv('PRIVSIG_SCHOOL_NAME','Moja szkoła')); db.add(s); db.flush()
        db.add(User(id=uid(),school_id=s.id,username='admin',name='Administrator',role='superadmin',password_hash=hasher.hash(password),class_ids=[],student_ids=[],disabled_apps=[],active=True))
    engine.dispose()
    print('Utworzono konto administratora. Hasło nie zostało wyświetlone.')

if __name__=='__main__': main()
