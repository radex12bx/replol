# PRIVSIG SCHOOL MOBILE — projekt iOS 0.1

To natywny klient SwiftUI dla iPhone'a i iPada (iOS 17 lub nowszy),
współpracujący z wcześniejszym API PRIVSIG SCHOOL OS. To nie jest obraz systemu
operacyjnego ani strona internetowa. Projekt nie został skompilowany w Xcode
ani uruchomiony na iPhonie. W paczce NIE MA instalowalnego pliku IPA.

## Funkcje w kodzie

- Logowanie do rzeczywistego serwera szkoły przez HTTPS; brak lokalnego wyboru roli.
- Plan lekcji sortowany według dnia i numeru lekcji, filtrowanie, zastępstwa.
- Oceny, frekwencja, sprawdziany, zadania domowe, oceny końcowe i uwagi.
- Wiadomości: odczyt, utworzenie i edycja zgodnie z regułami API.
- 15 modułów szkolnych; 13 ról pochodzi z kont na serwerze.
- Formularze dodawania, edycji, usuwania i historia zmian rekordów.
- Admin: tworzenie i edycja kont, role, przypisane klasy/uczniowie, wyłączanie
  aplikacji, dezaktywowanie kont, tworzenie szkół i odczyt audytu.
- Raporty i powiadomienia z API. APNs/push w tle nie jest zaimplementowane.
- WebSocket WSS odświeża listy po zmianach; przy utracie połączenia aplikacja
  pokazuje status i pozwala połączyć się ponownie/odświeżyć ręcznie.

Uprawnienie do zapisu modułu nie daje prawa do każdego wpisu. Serwer dodatkowo
sprawdza klasę, ucznia, szkołę, autora i opiekuna poufnej sprawy. Nie każdy
pracownik może zmieniać wszystko. Superadmin także nie otrzymuje automatycznie
dostępu do danych psychologicznych ani prywatnych wiadomości.

## Otwieranie i budowa IPA na Macu

1. Rozpakuj ZIP. Otwórz `PRIVSIGMobile.xcodeproj` w Xcode na macOS.
2. W Signing & Capabilities wybierz własny Team. W razie potrzeby zmień
   Bundle Identifier `pl.privsig.school.mobile` na unikalny identyfikator.
3. Najpierw zbuduj i przetestuj aplikację w symulatorze oraz na iPhonie.
4. Wybierz urządzenie docelowe iOS, następnie Product → Archive.
5. W Organizer wybierz Distribute App, odpowiednią metodę dystrybucji
   i eksport. Xcode utworzy podpisany plik `.ipa`, jeśli konto i profil
   podpisywania pozwalają na wybraną metodę. Nie wysyłaj nam kluczy ani hasła Apple.

Podpis i profil muszą pasować do urządzenia i sposobu dystrybucji.
Samo przemianowanie ZIP na IPA nie tworzy działającej aplikacji.

## Serwer i konta

W aplikacji wpisz adres HTTPS istniejącego serwera szkoły; nie ma wbudowanego
serwera publicznego. Adres 127.0.0.1 na iPhonie oznacza sam telefon.
Backend jest dołączony w `Server/privsig`, a wdrożenie PostgreSQL/Caddy
w `Server/deploy`. Jeśli masz wcześniejszy serwer, użyj jego adresu i kont.
Nie uruchamiaj drugiej bazy, jeśli chcesz te same dane co na komputerach.

Do lokalnych testów backendu:
```
cd Server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-server.txt
python -m privsig.server.main --demo
```
Lokalny tryb demo HTTP służy testom backendu i nie jest bezpośrednio dostępny
z klienta iOS wymagającego HTTPS. Centralne wdrożenie wymaga PostgreSQL,
konfiguracji TLS oraz utworzenia pierwszego administratora przez
`python -m privsig.server.bootstrap` (sprawdź `--help`). Przykładowy Docker Compose
nie został przetestowany w ramach tego wydania mobilnego.

Lokalne fikcyjne konta: admin, dyrektor, wicedyrektor, nauczyciel, wychowawca,
wozny, sekretariat, pedagog, psycholog, bibliotekarz, it, uczen, rodzic.
W lokalnym demo hasło: `PrivsigDemo!2026`. Konta te nie istnieją automatycznie
na serwerze produkcyjnym. Student i rodzic odczytują przypisane dane,
nauczyciel edytuje dane swoich klas, sekretariat może zmieniać plan lekcji.

## Dane i bezpieczeństwo

Hasło i token sesji pozostają w pamięci klienta, nie w UserDefaults. Po ponownym
uruchomieniu trzeba zalogować się ponownie. Zapisany jest tylko adres serwera.
Sesja URLSession jest ephemeral. Nie wyłączono ATS ani kontroli certyfikatów.
Serwer odrzuca niedozwolone operacje i konflikty wersji (409). Obsługa eksportu
raportów do plików, załączników, Face ID, powiadomień APNs i pracy offline
nie jest częścią tej wersji. Nie deklarujemy gotowości do produkcji/zgodności
RODO bez osobnego wdrożenia i oceny organizacyjnej.

## Testy

`tests/test_mobile_contract.py` sprawdza backend używany przez klienta:
13 ról, zakres ucznia, blokowanie zapisu, zmianę oceny i widoczność dla rodzica,
konflikt wersji, zmianę planu, konta oraz uwierzytelnienie WebSocket.
Wyniki rzeczywistego uruchomienia są w `TEST-REPORT.json`.
Testy te NIE zastępują kompilacji i testów interfejsu iOS.

Dokumentacja Apple:
https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices
https://help.apple.com/xcode/mac/current/en.lproj/dev23ea8b877.html
