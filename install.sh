#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/aw2724dm-control"
COMMAND_LINK="/usr/local/bin/aw2724dm-control"
DESKTOP_FILE="/usr/share/applications/aw2724dm-control.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/aw2724dm-control.svg"

if [[ ${EUID} -eq 0 && -z ${SUDO_USER:-} ]]; then
    echo "Bu betiği normal kullanıcı hesabınızdan ./install.sh olarak çalıştırın; betik gerektiğinde sudo ister." >&2
    exit 1
fi

INSTALL_USER="${SUDO_USER:-${USER}}"
if ! getent passwd "${INSTALL_USER}" >/dev/null; then
    echo "Kurulum kullanıcısı bulunamadı: ${INSTALL_USER}" >&2
    exit 1
fi

for required in requirements.txt apt-requirements.txt pyproject.toml src packaging/45-aw2724dm-control-i2c.rules packaging/i2c-dev.conf packaging/aw2724dm-control.desktop packaging/aw2724dm-control-launcher packaging/aw2724dm-update packaging/release-public-key.pem; do
    if [[ ! -e "${PROJECT_DIR}/${required}" ]]; then
        echo "Eksik proje bileşeni: ${required}" >&2
        exit 1
    fi
done

mapfile -t APT_PACKAGES < <(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "${PROJECT_DIR}/apt-requirements.txt")

echo "[1/7] Ubuntu paketleri kuruluyor…"
sudo apt-get update
sudo apt-get install -y "${APT_PACKAGES[@]}"

echo "[2/7] i2c-dev ve kullanıcı izinleri yapılandırılıyor…"
if ! getent group i2c >/dev/null; then
    sudo groupadd --system i2c
fi
sudo install -m 0644 "${PROJECT_DIR}/packaging/i2c-dev.conf" /etc/modules-load.d/i2c-dev.conf
sudo modprobe i2c-dev
sudo usermod -aG i2c "${INSTALL_USER}"
sudo install -m 0644 "${PROJECT_DIR}/packaging/45-aw2724dm-control-i2c.rules" /etc/udev/rules.d/45-aw2724dm-control-i2c.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=i2c

echo "[3/7] Uygulama /opt altına kopyalanıyor…"
sudo install -d -m 0755 "${INSTALL_DIR}" "${INSTALL_DIR}/src" "${INSTALL_DIR}/packaging"
sudo cp -a "${PROJECT_DIR}/src/." "${INSTALL_DIR}/src/"
sudo install -m 0644 "${PROJECT_DIR}/requirements.txt" "${INSTALL_DIR}/requirements.txt"
sudo install -m 0644 "${PROJECT_DIR}/pyproject.toml" "${INSTALL_DIR}/pyproject.toml"
sudo install -m 0644 "${PROJECT_DIR}/packaging/aw2724dm-control.desktop" "${INSTALL_DIR}/packaging/aw2724dm-control.desktop"
sudo install -m 0755 "${PROJECT_DIR}/packaging/aw2724dm-control-launcher" "${INSTALL_DIR}/aw2724dm-control"
sudo install -m 0755 "${PROJECT_DIR}/packaging/aw2724dm-update" "${INSTALL_DIR}/aw2724dm-update"
sudo install -m 0644 "${PROJECT_DIR}/packaging/release-public-key.pem" "${INSTALL_DIR}/release-public-key.pem"
sudo chown -R root:root "${INSTALL_DIR}"

echo "[4/7] Python sanal ortamı hazırlanıyor…"
if [[ ! -x "${INSTALL_DIR}/venv/bin/python" ]]; then
    sudo python3 -m venv "${INSTALL_DIR}/venv"
fi
sudo "${INSTALL_DIR}/venv/bin/python" -m pip install --upgrade pip setuptools
sudo "${INSTALL_DIR}/venv/bin/python" -m pip install --requirement "${INSTALL_DIR}/requirements.txt"
sudo "${INSTALL_DIR}/venv/bin/python" -m pip install --no-build-isolation --no-deps --editable "${INSTALL_DIR}"

echo "[5/7] Komut ve masaüstü girdisi kuruluyor…"
sudo ln -sfn "${INSTALL_DIR}/aw2724dm-control" "${COMMAND_LINK}"
sudo install -m 0644 "${PROJECT_DIR}/packaging/aw2724dm-control.desktop" "${DESKTOP_FILE}"
sudo install -m 0644 "${PROJECT_DIR}/src/assets/aw2724dm-control.svg" "${ICON_FILE}"
if command -v update-desktop-database >/dev/null 2>&1; then
    sudo update-desktop-database /usr/share/applications
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null || true
fi

echo "[6/7] Kurulum doğrulanıyor…"
"${COMMAND_LINK}" --version

echo "[7/7] Kurulum tamamlandı."
echo
echo "ÖNEMLİ: i2c grup üyeliğinin etkinleşmesi için GNOME oturumunu kapatıp yeniden açın."
echo "Uygulama GNOME Wayland ve X11/Xorg oturumlarını destekler."
echo "Ardından uygulama menüsünden 'AW2724DM Monitor Control'ı veya terminalden aw2724dm-control komutunu başlatın."
