"""Shared UI vocabulary. Authoritative authorization lives in server.policy."""
ROLES = {
    'superadmin': 'Superadministrator', 'director': 'Dyrektor',
    'deputy': 'Wicedyrektor', 'teacher': 'Nauczyciel', 'tutor': 'Wychowawca',
    'janitor': 'Woźny', 'office': 'Sekretariat', 'pedagogue': 'Pedagog',
    'psychologist': 'Psycholog', 'librarian': 'Bibliotekarz', 'it': 'Administrator IT',
    'student': 'Uczeń', 'parent': 'Rodzic',
}
# id, name, icon monogram, accent, description, resources
APPS = {
 'grades': ('Dziennik', 'Dz', '#76b8ff', 'Oceny i obecności, w jednym miejscu.', ['grades','attendance','assessments','homework','finals']),
 'notes': ('Uwagi', 'Uw', '#ffa575', 'Pochwały, uwagi i zachowanie.', ['notes']),
 'messenger': ('Messenger', 'Ms', '#79dcc5', 'Rozmowy w społeczności szkoły.', ['messages']),
 'director': ('Dyrektor', 'Dy', '#b8a2ff', 'Organizacja i zadania szkoły.', ['school_tasks']),
 'teacher': ('Nauczyciel', 'Na', '#93c5ff', 'Twoje klasy i codzienne lekcje.', ['attendance','grades','homework','assessments','finals']),
 'janitor': ('Woźny', 'Wo', '#ffc36b', 'Naprawy, klucze i zadania.', ['maintenance']),
 'office': ('Sekretariat', 'Se', '#95d8ce', 'Wnioski i dokumentacja szkolna.', ['office_records']),
 'plan': ('Plan', 'Pl', '#f2b9f9', 'Lekcje oraz zastępstwa.', ['timetable','substitutions']),
 'calendar': ('Kalendarz', 'Ka', '#ffaaa7', 'Wydarzenia, zebrania, terminy.', ['events']),
 'files': ('Files', 'Fi', '#91bbff', 'Dokumenty szkolne i pliki lokalne.', ['documents']),
 'admin': ('Admin', 'Ad', '#b9aeff', 'Konta, szkoły, uprawnienia i audyt.', []),
 'library': ('Biblioteka', 'Bi', '#d4c483', 'Katalog książek i wypożyczenia.', ['books','loans']),
 'pedagogue': ('Pedagog', 'Pe', '#dfa6cc', 'Sprawy pod opieką specjalistów.', ['cases']),
 'it': ('IT', 'IT', '#86d9ff', 'Zgłoszenia i wsparcie techniczne.', ['tickets']),
 'reports': ('Reports', 'Rp', '#a0dbad', 'Średnie, frekwencja i eksport CSV.', []),
}

def f(key, label, kind='text', options=None, required=True):
    return {'key':key, 'label':label, 'kind':kind, 'options':options or [], 'required':required}

STUDENT = f('student_id','Uczeń','student')
CLASS = f('class_id','Klasa','class')
SUBJECT = f('subject','Przedmiot','choice',['Matematyka','Język polski','Język angielski','Historia','Biologia','Informatyka','Fizyka','Chemia','WF'])
DATE = f('date','Data','date')
DESCRIPTION = f('description','Opis','long',required=False)
RESOURCES = {
 'grades': ('Oceny', [STUDENT,CLASS,SUBJECT,f('value','Ocena 1–6','int'),f('modifier','Plus / minus','choice',['','+','-']),f('weight','Waga','int'),f('category','Kategoria','choice',['Sprawdzian','Kartkówka','Odpowiedź','Aktywność','Praca domowa']),DATE,DESCRIPTION]),
 'attendance': ('Frekwencja',[STUDENT,CLASS,SUBJECT,DATE,f('lesson','Numer lekcji','int'),f('status','Status','choice',['Obecny','Nieobecny','Spóźnienie','Usprawiedliwiony'])]),
 'assessments': ('Sprawdziany',[CLASS,SUBJECT,f('title','Temat'),DATE,DESCRIPTION]),
 'homework': ('Zadania domowe',[CLASS,SUBJECT,f('title','Zadanie'),f('date','Termin oddania','date'),DESCRIPTION]),
 'finals': ('Oceny końcowe',[STUDENT,CLASS,SUBJECT,f('value','Ocena końcowa','int'),f('period','Okres','choice',['Semestr 1','Semestr 2','Roczna']),DATE]),
 'notes': ('Uwagi i pochwały',[STUDENT,CLASS,f('kind','Rodzaj','choice',['Pochwała','Uwaga','Zachowanie']),f('title','Treść'),DATE]),
 'messages': ('Wiadomości',[f('recipient_id','Odbiorca','user'),f('title','Temat'),f('body','Wiadomość','long')]),
 'school_tasks': ('Zadania szkoły',[f('title','Zadanie'),f('assignee_id','Osoba odpowiedzialna','user'),DATE,f('status','Status','choice',['Nowe','W toku','Gotowe']),DESCRIPTION]),
 'maintenance': ('Naprawy i klucze',[f('title','Zadanie'),f('room','Sala / miejsce'),f('kind','Rodzaj','choice',['Naprawa','Klucze','Porządek','Inne']),f('assignee_id','Wykonawca','user'),f('status','Status','choice',['Nowe','W toku','Gotowe']),DATE,DESCRIPTION]),
 'office_records': ('Dokumentacja',[f('title','Nazwa'),f('kind','Rodzaj','choice',['Wniosek','Zaświadczenie','Rekrutacja','Korespondencja']),f('status','Status','choice',['Nowe','W toku','Wydane','Archiwum']),DATE,DESCRIPTION]),
 'timetable': ('Plan lekcji',[CLASS,SUBJECT,f('day','Dzień','choice',['Poniedziałek','Wtorek','Środa','Czwartek','Piątek']),f('lesson','Lekcja','int'),f('room','Sala'),f('teacher_id','Nauczyciel','user')]),
 'substitutions': ('Zastępstwa',[CLASS,SUBJECT,DATE,f('lesson','Lekcja','int'),f('teacher_id','Zastępujący','user'),f('room','Sala'),DESCRIPTION]),
 'events': ('Wydarzenia',[f('title','Wydarzenie'),DATE,f('time','Godzina (HH:MM)'),f('location','Miejsce'),DESCRIPTION]),
 'documents': ('Dokumenty',[f('title','Nazwa pliku'),f('audience','Dostęp','choice',['Prywatny','Pracownicy','Klasa']),f('class_id','Klasa (dla dostępu Klasa)','class',required=False),f('body','Treść dokumentu tekstowego','long',required=False)]),
 'books': ('Katalog książek',[f('title','Tytuł'),f('author','Autor'),f('isbn','ISBN / identyfikator'),f('copies','Egzemplarze','int')]),
 'loans': ('Wypożyczenia',[STUDENT,f('book_id','Książka','book'),DATE,f('due_date','Termin zwrotu','date'),f('status','Status','choice',['Wypożyczona','Zwrócona'])]),
 'cases': ('Sprawy specjalistyczne',[STUDENT,f('kind','Rodzaj','choice',['Wychowawcza','Psychologiczna','Medyczna']),f('assignee_id','Opiekun sprawy','user'),f('title','Sprawa'),f('status','Status','choice',['Otwarta','W toku','Zamknięta']),f('description','Poufna notatka','long')]),
 'tickets': ('Zgłoszenia IT',[f('title','Problem'),f('device','Urządzenie / sala'),f('priority','Priorytet','choice',['Niski','Normalny','Wysoki']),f('status','Status','choice',['Nowe','W toku','Rozwiązane']),DESCRIPTION]),
}

ACADEMIC = {'grades','attendance','assessments','homework','finals','notes'}
SELF_ACADEMIC = {'grades','attendance','finals','notes'}
CLASS_RECORDS = ACADEMIC | {'timetable','substitutions'}

