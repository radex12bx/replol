# PRIVSIG — działający serwer aplikacji iOS i desktop

Serwer testowy został uruchomiony 9 października 2026:
https://privsig-school-api.onrender.com

W aplikacji iPhone wpisz powyższy adres HTTPS w polu serwera, login `admin`
(superadministrator) lub `uczen` (uczeń), oraz indywidualne hasło przekazane
w rozmowie. Hasła nie znajdują się w publicznym repozytorium. Uczeń widzi plan,
oceny i aplikacje przypisane do swojej roli. Administrator zarządza modułami
oraz kontami w aplikacji Admin. Pozostałe konta mają niepublikowane hasła;
administrator może nadać im nowe hasła.

Usługi w Render / My Workspace / Frankfurt:
- API: srv-db4g9f3l550s73blge1g, plan free, Docker, kontrola /health;
- PostgreSQL 16: dpg-db4g3f4s728c73ali8gg-a, plan free, połączenie wewnętrzne.

Sprawdzone na wdrożonym serwerze: HTTPS /health i PostgreSQL, logowanie obu
kont, /me, plan ucznia, blokada zmiany ocen przez ucznia (403), uwierzytelniony
WebSocket ping/pong oraz odrzucenie wspólnego lokalnego hasła demo (401).
GitHub Actions: cztery testy backendu zakończone powodzeniem z PostgreSQL.
Nie oznacza to testu instalacji ani pracy IPA na fizycznym iPhone.

Baza zawiera wyłącznie fikcyjną szkołę i dane testowe. Usługa nie jest
zatwierdzona do produkcyjnego przetwarzania danych uczniów. Bezpłatna baza
wygasa 8 listopada 2026; przed tym terminem potrzebna jest decyzja o dalszym
hostingu i kopii danych. Darmowa usługa może zasypiać; pierwsze połączenie
może potrwać około minuty — wtedy ponów logowanie.

Usługi utworzono narzędziami Render. render.yaml pozostaje szablonem dla
osobnego wdrożenia; nie uruchamiaj go ponownie dla tych samych usług.
Konfiguracja początkowych haseł jest używana wyłącznie przy pustej bazie.
Ponowne uruchomienia nie zastępują kont ani istniejących danych.
