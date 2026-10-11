#!/bin/sh
# Сборка TalkMate и установка на подключённый iPhone.
#
# Один раз до запуска:
#   1. Xcode → Settings → Accounts → «+» → Apple ID. Подойдёт обычная бесплатная учётная запись.
#   2. На iPhone: Настройки → Конфиденциальность и безопасность → Режим разработчика → включить, телефон перезагрузится.
#   3. Подключить iPhone кабелем и ответить «Доверять» на вопрос о компьютере.
#
# Запуск:  ./install_on_iphone.sh            (команда разработчика и телефон определяются сами)
#          TEAM_ID=ABCDE12345 ./install_on_iphone.sh
set -e
cd "$(dirname "$0")"

# Номер команды Xcode хранит в своих настройках; название ключа зависит от версии, поэтому ищем по всем.
TEAM_ID="${TEAM_ID:-$(defaults read com.apple.dt.Xcode 2>/dev/null | grep -m1 'teamID' | sed 's/.*= *//; s/[";]//g')}"
if [ -z "$TEAM_ID" ]; then
    echo "В Xcode не найдена учётная запись разработчика."
    echo "Откройте Xcode → Settings → Accounts, добавьте Apple ID и запустите скрипт снова."
    exit 1
fi

# У телефона два номера: по первому с ним работает devicectl, второй (UDID) нужен xcodebuild.
INFO="$(mktemp)"
xcrun devicectl list devices --json-output "$INFO" >/dev/null 2>&1 || true
read -r DEVICE_ID DEVICE_UDID DEV_MODE <<DEVICE
$(python3 - "$INFO" <<'PY'
import json, sys
try:
    devices = json.load(open(sys.argv[1]))["result"]["devices"]
except Exception:
    devices = []
for device in devices:
    hardware, props, link = device["hardwareProperties"], device["deviceProperties"], device["connectionProperties"]
    if hardware.get("deviceType") == "iPhone" and link.get("tunnelState") != "unavailable":
        print(device["identifier"], hardware.get("udid", ""), props.get("developerModeStatus", ""))
        break
PY
)
DEVICE
rm -f "$INFO"
if [ -z "$DEVICE_ID" ]; then
    echo "Подключённый iPhone не найден. Подключите телефон кабелем и разблокируйте его."
    exit 1
fi
if [ "$DEV_MODE" != "enabled" ]; then
    echo "На iPhone выключен режим разработчика."
    echo "Включите: Настройки → Конфиденциальность и безопасность → Режим разработчика. Телефон перезагрузится"
    echo "и после разблокировки спросит подтверждение. Затем запустите скрипт снова."
    exit 1
fi

# Адрес этого компьютера в локальной сети: телефон должен быть в той же сети Wi-Fi, что и сервер.
HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)}"
SERVER_URL="${SERVER_URL:-http://${HOST_IP:-localhost}:5050}"
# У бесплатной учётной записи идентификатор приложения должен быть уникальным, поэтому в него добавлен номер команды.
BUNDLE_ID="${BUNDLE_ID:-ru.itmo.talkmate.$(echo "$TEAM_ID" | tr 'A-Z' 'a-z')}"

echo "Команда: $TEAM_ID, телефон: $DEVICE_ID, сервер: $SERVER_URL"
xcodegen generate >/dev/null
xcodebuild -project TalkMate.xcodeproj -scheme TalkMate -configuration Debug \
    -destination "id=$DEVICE_UDID" -derivedDataPath build/device -allowProvisioningUpdates -allowProvisioningDeviceRegistration \
    DEVELOPMENT_TEAM="$TEAM_ID" CODE_SIGN_STYLE=Automatic PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    TALKMATE_SERVER_URL="$SERVER_URL" build | grep -E "error:|warning: Signing|BUILD" || true

APP="build/device/Build/Products/Debug-iphoneos/TalkMate.app"
[ -d "$APP" ] || { echo "Сборка не удалась, приложение не создано."; exit 1; }
xcrun devicectl device install app --device "$DEVICE_ID" "$APP"
xcrun devicectl device process launch --device "$DEVICE_ID" "$BUNDLE_ID" || true
echo "Готово. Если приложение не открылось: Настройки → Основные → VPN и управление устройством → доверять разработчику."
