#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "$(uname -s)" != Darwin ] || ! command -v xcodebuild >/dev/null 2>&1; then
    echo "Brak macOS/Xcode. Nie utworzono IPA." >&2
    exit 1
fi
xcrun --sdk iphoneos --show-sdk-path >/dev/null
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/privsig-unsigned.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT HUP INT TERM
xcodebuild -project PRIVSIGMobile.xcodeproj -scheme PRIVSIGMobile \
    -configuration Release -destination 'generic/platform=iOS' \
    -derivedDataPath "$scratch_dir/DerivedData" \
    SDKROOT=iphoneos CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
    CODE_SIGN_IDENTITY= DEVELOPMENT_TEAM= build
app="$scratch_dir/DerivedData/Build/Products/Release-iphoneos/PRIVSIGMobile.app"
[ -d "$app" ] || { echo "Nie znaleziono skompilowanej aplikacji." >&2; exit 1; }
executable=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app/Info.plist")
[ -n "$executable" ] && [ -f "$app/$executable" ] || { echo "Brak pliku wykonywalnego." >&2; exit 1; }
/usr/bin/file "$app/$executable" | /usr/bin/grep -q 'Mach-O' || { echo "Plik nie jest aplikacja Mach-O." >&2; exit 1; }
/usr/bin/lipo -archs "$app/$executable" | /usr/bin/grep -q 'arm64' || { echo "Brak architektury arm64 dla iPhone." >&2; exit 1; }
mkdir -p "$scratch_dir/Payload" build
/usr/bin/ditto "$app" "$scratch_dir/Payload/PRIVSIGMobile.app"
output="$PWD/build/PRIVSIGMobile-unsigned.ipa"
if [ -e "$output" ]; then
    echo "Plik build/PRIVSIGMobile-unsigned.ipa juz istnieje. Przenies go przed ponowna budowa." >&2
    exit 1
fi
/usr/bin/ditto -c -k --norsrc --noextattr --keepParent "$scratch_dir/Payload" "$output"
/usr/bin/unzip -t "$output"
echo "Utworzono: $output"
echo "To paczka bez podpisu dystrybucyjnego. Podpisz ja wlasna metoda przed instalacja."
