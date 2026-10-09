import re
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select
from privsig.catalog import RESOURCES, APPS, ROLES
from .db import User, Student, SchoolClass, Record
from .policy import visible_students, LEAD, STAFF

def bad(message):
    raise HTTPException(422,message)

def validate_data(module, data, db, user, existing=None):
    fields=RESOURCES[module][1]
    keys={f['key'] for f in fields}
    if set(data)-keys: bad('Nieznane pola dokumentu.')
    cleaned={}
    for field in fields:
        key=field['key']; value=data.get(key,'')
        if value is None: value=''
        if value=='' and field['required'] and not (field['kind']=='choice' and '' in field['options']):
            bad('Uzupełnij: '+field['label'])
        if field['kind']=='int':
            if type(value) is not int: bad(field['label']+': wymagana liczba całkowita.')
            if not 1<=value<=10000: bad(field['label']+': poza zakresem.')
        elif not isinstance(value,str): bad(field['label']+': wymagany tekst.')
        else:
            if len(value)>(15000 if field['kind']=='long' else 300): bad(field['label']+': zbyt długi tekst.')
            if field['kind']=='choice' and value not in field['options']: bad('Nieprawidłowa opcja: '+field['label'])
            if field['kind']=='date':
                try: date.fromisoformat(value)
                except ValueError: bad('Data musi mieć format RRRR-MM-DD.')
        cleaned[key]=value
    if module in {'grades','finals'} and not 1<=cleaned['value']<=6: bad('Ocena musi być w zakresie 1–6.')
    if module=='grades' and not 1<=cleaned['weight']<=10: bad('Waga musi być w zakresie 1–10.')
    if 'lesson' in cleaned and not 1<=cleaned['lesson']<=16: bad('Numer lekcji: 1–16.')
    if module=='events' and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',cleaned['time']): bad('Godzina musi mieć format HH:MM.')
    if cleaned.get('class_id'):
        cls=db.get(SchoolClass,cleaned['class_id'])
        if not cls or cls.school_id!=user.school_id: bad('Nieprawidłowa klasa.')
        if user.role not in LEAD|{'office','librarian'} and cls.id not in user.class_ids: bad('Klasa nie jest przypisana do konta.')
    if cleaned.get('student_id'):
        s=db.get(Student,cleaned['student_id'])
        if not s or s.school_id!=user.school_id or not visible_students(user,[s]): bad('Uczeń nie jest przypisany do konta.')
        if cleaned.get('class_id') and s.class_id!=cleaned['class_id']: bad('Uczeń należy do innej klasy.')
    for key in ('recipient_id','assignee_id','teacher_id'):
        if cleaned.get(key):
            target=db.get(User,cleaned[key])
            if not target or target.school_id!=user.school_id or not target.active: bad('Nieprawidłowe konto odbiorcy.')
            if key=='teacher_id' and target.role not in {'teacher','tutor','director','deputy'}: bad('Wybierz nauczyciela.')
    if module=='cases':
        target=db.get(User,cleaned['assignee_id'])
        required_role='psychologist' if cleaned['kind'] in {'Psychologiczna','Medyczna'} else 'pedagogue'
        if target.role!=required_role or target.id!=user.id: bad('Sprawa wymaga przypisanego konta specjalisty.')
    if module=='tickets' and user.role not in LEAD|{'it'}:
        if cleaned['status']!='Nowe': bad('Status zgłoszenia może zmieniać administrator IT.')
        if existing: bad('Zgłoszenie po wysłaniu obsługuje administrator IT.')
    if module=='documents':
        if cleaned['audience']=='Pracownicy' and user.role not in STAFF: bad('Dokumenty pracowników są ograniczone do pracowników.')
        if cleaned['audience']=='Klasa' and not cleaned.get('class_id'): bad('Wybierz klasę dokumentu.')
    rows=list(db.scalars(select(Record).where(Record.school_id==user.school_id,Record.module==module,Record.deleted.is_(False))))
    unique = {
        'attendance':('student_id','date','lesson'),
        'finals':('student_id','subject','period'),
        'timetable':('class_id','day','lesson'),
        'substitutions':('class_id','date','lesson'),
        'books':('isbn',),
    }.get(module)
    if unique and any(r.id!=(existing.id if existing else None) and all(r.data.get(k)==cleaned[k] for k in unique) for r in rows):
        raise HTTPException(409,'Taki wpis już istnieje. Edytuj istniejący rekord.')
    if module=='loans':
        book=db.get(Record,cleaned['book_id'])
        if not book or book.module!='books' or book.school_id!=user.school_id or book.deleted: bad('Nieprawidłowa książka.')
        if date.fromisoformat(cleaned['due_date'])<date.fromisoformat(cleaned['date']): bad('Termin zwrotu jest wcześniejszy niż wypożyczenie.')
        active=[r for r in rows if r.id!=(existing.id if existing else None) and r.data['book_id']==book.id and r.data['status']=='Wypożyczona']
        if cleaned['status']=='Wypożyczona' and len(active)>=book.data['copies']: raise HTTPException(409,'Brak dostępnych egzemplarzy.')
        if cleaned['status']=='Wypożyczona' and any(r.data['student_id']==cleaned['student_id'] for r in active): raise HTTPException(409,'Uczeń już wypożyczył tę książkę.')
    if module=='books' and existing:
        active=list(db.scalars(select(Record).where(Record.school_id==user.school_id,Record.module=='loans',Record.deleted.is_(False))))
        if sum(r.data['book_id']==existing.id and r.data['status']=='Wypożyczona' for r in active)>cleaned['copies']:
            bad('Liczba egzemplarzy jest mniejsza niż aktywne wypożyczenia.')
    return cleaned

def validate_user_scopes(db, school_id, class_ids, student_ids, disabled_apps, role):
    if role not in ROLES: bad('Nieznana rola.')
    if set(disabled_apps)-set(APPS): bad('Nieznana aplikacja.')
    for cid in class_ids:
        obj=db.get(SchoolClass,cid)
        if not obj or obj.school_id!=school_id: bad('Nieprawidłowa klasa konta.')
    for sid in student_ids:
        obj=db.get(Student,sid)
        if not obj or obj.school_id!=school_id: bad('Nieprawidłowe powiązanie ucznia.')
        if obj.class_id not in class_ids: bad('Dodaj klasę powiązanego ucznia do konta.')
    if role=='student' and len(student_ids)!=1: bad('Konto ucznia wymaga dokładnie jednego ucznia.')
    if role=='parent' and not student_ids: bad('Konto rodzica wymaga powiązanego ucznia.')
