"""Explicit, fictitious demo data. Never called in production mode."""
from datetime import date, timedelta
from sqlalchemy import select
from .db import School, SchoolClass, Student, User, Record, Revision, uid, now
from privsig.catalog import ROLES

DEMO_PASSWORD='PrivsigDemo!2026'
NAMES={'superadmin':('admin','Alex Privsig'),'director':('dyrektor','Joanna Przykładowa'),
 'deputy':('wicedyrektor','Paweł Testowy'),'teacher':('nauczyciel','Anna Demo'),
 'tutor':('wychowawca','Marek Przykład'),'janitor':('wozny','Tomasz Demo'),
 'office':('sekretariat','Ewa Testowa'),'pedagogue':('pedagog','Katarzyna Demo'),
 'psychologist':('psycholog','Michał Testowy'),'librarian':('bibliotekarz','Olga Przykład'),
 'it':('it','Daniel Demo'),'student':('uczen','Zofia Testowa'),'parent':('rodzic','Barbara Testowa')}

def seed_demo(factory, passwords=None):
    from .api import hasher
    with factory.begin() as db:
        if db.scalar(select(School).limit(1)): return
        school=School(id=uid(),name='Szkoła Demonstracyjna PRIVSIG'); other=School(id=uid(),name='Druga Szkoła Testowa')
        db.add_all([school,other]); db.flush()
        a=SchoolClass(id=uid(),school_id=school.id,name='7A'); b=SchoolClass(id=uid(),school_id=school.id,name='7B')
        c=SchoolClass(id=uid(),school_id=other.id,name='8A'); db.add_all([a,b,c]); db.flush()
        students=[Student(id=uid(),school_id=school.id,class_id=a.id,name=n) for n in ['Zofia Testowa','Adam Przykład','Lena Demo','Filip Testowy']]
        students.append(Student(id=uid(),school_id=school.id,class_id=b.id,name='Jan Inna Klasa'))
        foreign=Student(id=uid(),school_id=other.id,class_id=c.id,name='Uczeń Drugiej Szkoły')
        db.add_all(students+[foreign]); db.flush()
        password_hash=hasher.hash(DEMO_PASSWORD); users={}
        for role,(username,name) in NAMES.items():
            u=User(id=uid(),school_id=school.id,username=username,name=name,role=role,password_hash=(hasher.hash(passwords[username]) if passwords else password_hash),active=True,
                   class_ids=[a.id] if role not in {'janitor','it'} else [],student_ids=[students[0].id] if role in {'student','parent'} else [],disabled_apps=[])
            db.add(u); users[role]=u
        foreign_user=User(id=uid(),school_id=other.id,username='nauczyciel2',name='Nauczyciel Drugiej Szkoły',role='teacher',password_hash=(hasher.hash(passwords['nauczyciel2']) if passwords else password_hash),class_ids=[c.id],student_ids=[],disabled_apps=[],active=True)
        db.add(foreign_user); db.flush()
        today=date.today(); d=today.isoformat()
        def add(module,data,role='teacher',sid=None,author=None):
            r=Record(id=uid(),school_id=sid or school.id,module=module,author_id=author or users[role].id,data=data,version=1,created_at=now(),updated_at=now(),deleted=False)
            db.add(r); db.flush(); db.add(Revision(record_id=r.id,actor_id=r.author_id,version=1,data=data)); return r
        for i,s in enumerate(students):
            for subject,value,modifier,weight in [('Matematyka',4+i%2,'+',3),('Język polski',5,'',2),('Język angielski',4,'-',1)]:
                add('grades',{'student_id':s.id,'class_id':s.class_id,'subject':subject,'value':value,'modifier':modifier,'weight':weight,'category':'Sprawdzian','date':d,'description':'Fikcyjne dane demonstracyjne'})
            add('attendance',{'student_id':s.id,'class_id':s.class_id,'subject':'Matematyka','date':d,'lesson':1,'status':'Obecny' if i!=2 else 'Nieobecny'})
        add('grades',{'student_id':foreign.id,'class_id':c.id,'subject':'Matematyka','value':6,'modifier':'','weight':2,'category':'Aktywność','date':d,'description':'Inna szkoła'},sid=other.id,author=foreign_user.id)
        add('notes',{'student_id':students[0].id,'class_id':a.id,'kind':'Pochwała','title':'Aktywne wsparcie projektu klasy.','date':d})
        add('finals',{'student_id':students[0].id,'class_id':a.id,'subject':'Matematyka','value':5,'period':'Semestr 1','date':d})
        add('assessments',{'class_id':a.id,'subject':'Matematyka','title':'Równania i proporcje','date':(today+timedelta(days=4)).isoformat(),'description':'Powtórz rozdział 3.'})
        add('homework',{'class_id':a.id,'subject':'Język polski','title':'Krótka recenzja książki','date':(today+timedelta(days=2)).isoformat(),'description':'Około 200 słów.'})
        add('messages',{'recipient_id':users['teacher'].id,'title':'Witaj w PRIVSIG','body':'Wszystkie dane w tej szkole są fikcyjne. Możesz swobodnie przetestować aplikacje.'},role='director')
        add('school_tasks',{'title':'Przygotować zebranie zespołu','assignee_id':users['office'].id,'date':d,'status':'W toku','description':'Sala konferencyjna, godz. 14:00.'},role='director')
        add('maintenance',{'title':'Sprawdzić projektor','room':'Sala 204','kind':'Naprawa','assignee_id':users['janitor'].id,'status':'Nowe','date':d,'description':'Sprawdzić zasilanie.'},role='director')
        add('maintenance',{'title':'Rejestr klucza do sali','room':'Sala 101','kind':'Klucze','assignee_id':users['janitor'].id,'status':'W toku','date':d,'description':'Wydano nauczycielowi, zwrot do 16:00.'},role='janitor')
        add('office_records',{'title':'Wniosek o zaświadczenie','kind':'Zaświadczenie','status':'W toku','date':d,'description':'Fikcyjny dokument sekretariatu.'},role='office')
        for lesson,subject,room in [(1,'Matematyka','204'),(2,'Język polski','101'),(3,'Informatyka','IT-1')]:
            add('timetable',{'class_id':a.id,'subject':subject,'day':'Poniedziałek','lesson':lesson,'room':room,'teacher_id':users['teacher'].id},role='director')
        add('substitutions',{'class_id':a.id,'subject':'Historia','date':d,'lesson':4,'teacher_id':users['tutor'].id,'room':'102','description':'Zastępstwo demonstracyjne.'},role='director')
        add('events',{'title':'Zebranie z rodzicami','date':(today+timedelta(days=5)).isoformat(),'time':'17:30','location':'Sala 204','description':'Klasa 7A.'},role='director')
        add('events',{'title':'Dzień nauki','date':(today+timedelta(days=12)).isoformat(),'time':'09:00','location':'Aula','description':'Projekty uczniowskie.'},role='director')
        add('documents',{'title':'Powitanie.txt','audience':'Pracownicy','class_id':'','body':'Witaj w PRIVSIG SCHOOL OS. To natywna aplikacja desktopowa Qt.\nDane demonstracyjne są fikcyjne.'},role='director')
        book=add('books',{'title':'Mały Książę','author':'Antoine de Saint-Exupéry','isbn':'DEMO-001','copies':3},role='librarian')
        add('books',{'title':'Atlas świata','author':'Redakcja demonstracyjna','isbn':'DEMO-002','copies':2},role='librarian')
        add('loans',{'student_id':students[0].id,'book_id':book.id,'date':d,'due_date':(today+timedelta(days=14)).isoformat(),'status':'Wypożyczona'},role='librarian')
        add('cases',{'student_id':students[1].id,'kind':'Wychowawcza','assignee_id':users['pedagogue'].id,'title':'Wsparcie organizacji nauki (DEMO)','status':'Otwarta','description':'Fikcyjna sprawa bez rzeczywistych danych osobowych.'},role='pedagogue')
        add('cases',{'student_id':students[0].id,'kind':'Psychologiczna','assignee_id':users['psychologist'].id,'title':'Rozmowa wspierająca (DEMO)','status':'Otwarta','description':'Poufny, całkowicie fikcyjny przykład.'},role='psychologist')
        add('tickets',{'title':'Drukarka nie odpowiada','device':'Sekretariat','priority':'Normalny','status':'Nowe','description':'Zgłoszenie demonstracyjne.'},role='office')
