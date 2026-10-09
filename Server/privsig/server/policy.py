"""Default-deny role + tenant + object authorization. Never trust UI filters."""
from privsig.catalog import APPS, ACADEMIC, SELF_ACADEMIC, CLASS_RECORDS

LEAD = {'superadmin','director','deputy'}
TEACH = LEAD | {'teacher','tutor'}
STAFF = LEAD | {'teacher','tutor','janitor','office','pedagogue','psychologist','librarian','it'}
READ = {
 **{x:TEACH|{'student','parent'} for x in ACADEMIC},
 'messages':STAFF|{'student','parent'}, 'school_tasks':LEAD|{'office'},
 'maintenance':LEAD|{'janitor'}, 'office_records':LEAD|{'office'},
 'timetable':STAFF|{'student','parent'}, 'substitutions':STAFF|{'student','parent'},
 'events':STAFF|{'student','parent'}, 'documents':STAFF|{'student','parent'},
 'books':STAFF|{'student','parent'}, 'loans':LEAD|{'librarian','student','parent'},
 'cases':{'pedagogue','psychologist'}, 'tickets':STAFF|{'student','parent'},
}
WRITE = {
 **{x:TEACH for x in ACADEMIC}, 'messages':READ['messages'],
 'school_tasks':LEAD|{'office'}, 'maintenance':LEAD|{'janitor'},
 'office_records':LEAD|{'office'}, 'timetable':LEAD|{'office'},
 'substitutions':LEAD|{'office'}, 'events':LEAD|{'office','teacher','tutor'},
 'documents':READ['documents'], 'books':LEAD|{'librarian'},
 'loans':LEAD|{'librarian'}, 'cases':{'pedagogue','psychologist'}, 'tickets':READ['tickets'],
}

def disabled_modules(user):
    # A module stays usable if at least one enabled app exposes it.
    enabled = set()
    exposed = set()
    for aid, info in APPS.items():
        exposed.update(info[4])
        if aid not in user.disabled_apps:
            enabled.update(info[4])
    return exposed - enabled

def permits(user, module, write=False):
    return user.active and module not in disabled_modules(user) and user.role in (WRITE if write else READ).get(module,set())

def allowed_apps(user):
    result=[]
    for aid,info in APPS.items():
        if aid in user.disabled_apps: continue
        if aid=='admin': ok=user.role in LEAD|{'it'}
        elif aid=='reports': ok=user.role in TEACH|{'student','parent'}
        elif aid=='teacher': ok=user.role in TEACH
        else: ok=any(permits(user,m) for m in info[4])
        if ok: result.append(aid)
    return result

def visible_students(user, students):
    if user.role in LEAD|{'office','librarian'}:
        return students
    if user.role in {'teacher','tutor','pedagogue','psychologist'}:
        return [s for s in students if s.class_id in user.class_ids]
    if user.role in {'student','parent'}:
        return [s for s in students if s.id in user.student_ids]
    return []

def object_allowed(user, module, data, author_id, write=False):
    if not permits(user,module,write): return False
    role=user.role
    if module in CLASS_RECORDS:
        if role in {'teacher','tutor'} and data.get('class_id') not in user.class_ids: return False
        if role in {'student','parent'}:
            if module in SELF_ACADEMIC:
                return data.get('student_id') in user.student_ids
            return data.get('class_id') in user.class_ids
    if module=='messages':
        if write: return author_id==user.id
        return author_id==user.id or data.get('recipient_id')==user.id
    if module=='documents':
        if write and author_id!=user.id and role not in LEAD: return False
        audience=data.get('audience')
        if audience=='Prywatny': return author_id==user.id
        if audience=='Pracownicy': return role in STAFF
        if audience=='Klasa': return data.get('class_id') in user.class_ids or role in LEAD
        return False
    if module=='cases':
        if data.get('assignee_id')!=user.id: return False
        if data.get('kind') in {'Psychologiczna','Medyczna'}: return role=='psychologist'
        return role=='pedagogue'
    if module=='loans' and role in {'student','parent'}:
        return data.get('student_id') in user.student_ids
    if module=='tickets' and role not in LEAD|{'it'}:
        return author_id==user.id
    return True
