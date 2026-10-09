# PRIVSIG — serwer aplikacji iOS i desktop

API jest zgodne z opublikowaną aplikacją IPA: HTTPS, logowanie, 13 ról,
plan, oceny, wiadomości, moduły szkolne i WebSocket. Dostęp i zakres danych
sprawdza backend. Baza PostgreSQL nie jest przechowywana na dysku aplikacji.

`render.yaml` przygotowuje usługę Docker i PostgreSQL w regionie Frankfurt.
Render zapewnia adres HTTPS. Konfiguracja pozostaje nieuruchomiona do czasu
połączenia konta Render i udanego wdrożenia. Nie ma jeszcze adresu logowania.

W pierwszym wdrożeniu ustaw dwa różne hasła (minimum 16 znaków):
- PRIVSIG_ADMIN_PASSWORD → login `admin`;
- PRIVSIG_STUDENT_PASSWORD → login `uczen`.

Nie umieszczaj haseł w repozytorium ani nie używaj lokalnego hasła demo.
Pozostałe fikcyjne konta mają indywidualne, niepublikowane hasła. Administrator
może nadać im nowe hasła w aplikacji: Aplikacje → Admin → Konta.
Po restarcie istniejące dane i hasła nie są zastępowane.

Inicjalizacja wstawia wyłącznie fikcyjną szkołę i dane testowe. Wydanie nie jest
zatwierdzone do produkcyjnego użycia z danymi uczniów. Wdrażanie rzeczywistej
szkoły wymaga oddzielnej konfiguracji, kopii zapasowych i oceny ochrony danych.

Plan free służy testom: usługa może zasypiać po 15 minutach bezczynności,
a bezpłatna baza PostgreSQL wygasa po 30 dniach. Pierwsze połączenie po uśpieniu
może wymagać odczekania i ponowienia logowania. Nie uruchamiaj płatnego planu,
jeśli go nie wybrałeś. Długoterminowe wdrożenie wymaga planu bazy bez tego limitu.

Po udanym wdrożeniu wpisz rzeczywisty adres HTTPS zwrócony przez Render
w aplikacji na iPhone. Rola wynika z konta. Nie ma lokalnego przełącznika
"jestem administratorem".

Dokumentacja:
https://render.com/docs/blueprint-spec
https://render.com/docs/free
