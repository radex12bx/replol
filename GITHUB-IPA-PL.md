# Budowa IPA na GitHub

Ten workflow buduje aplikację na maszynie macOS z Xcode bez certyfikatu,
bez Apple Team i bez przekazywania sekretów. IPA podpisujesz samodzielnie.
Budowa jeszcze nie została uruchomiona — plik IPA powstanie tylko po udanej
kompilacji projektu.

W repozytorium pliki projektu muszą znajdować się bezpośrednio w katalogu
głównym, nie pod dodatkowym folderem PRIVSIG-iPhone. Plik workflow musi mieć
ścieżkę `.github/workflows/build-ios-ipa.yml` na domyślnej gałęzi repozytorium.

1. Umieść zawartość folderu PRIVSIG-iPhone w swoim repozytorium GitHub.
2. Otwórz Actions → Build PRIVSIG unsigned IPA → Run workflow.
3. Po pomyślnym zakończeniu pobierz artefakt PRIVSIGMobile-unsigned-IPA.
4. Rozpakuj pobrany artefakt. W środku będzie PRIVSIGMobile-unsigned.ipa.
5. Podpisz IPA swoją metodą przed instalacją na iPhone.

W razie błędu kompilacji pobierz PRIVSIG-iOS-build-log. Nie zmieniaj nazwy
paczki źródłowej ZIP na IPA. Workflow sprawdza narzędzia Apple i obecność
skompilowanego pliku arm64. GitHub nie podpisuje tego wydania za Ciebie.

Dokumentacja:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch
https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts
