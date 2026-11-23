#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="/opt/aw2724dm-control"
COMMAND_LINK="/usr/local/bin/aw2724dm-control"
DESKTOP_FILE="/usr/share/applications/aw2724dm-control.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/aw2724dm-control.svg"

PURGE_CONFIG=false
if [[ ${1:-} == "--purge" ]]; then
    PURGE_CONFIG=true
elif [[ $# -gt 0 ]]; then
    echo "Kullanım: ./uninstall.sh [--purge]" >&2
    exit 2
fi

sudo rm -f -- "${COMMAND_LINK}" "${DESKTOP_FILE}" "${ICON_FILE}"
sudo rm -rf -- "${INSTALL_DIR}"
sudo rm -f -- /etc/udev/rules.d/45-aw2724dm-control-i2c.rules
sudo rm -f -- /etc/modules-load.d/i2c-dev.conf
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=i2c

if command -v update-desktop-database >/dev/null 2>&1; then
    sudo update-desktop-database /usr/share/applications
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null || true
fi

if [[ ${PURGE_CONFIG} == true ]]; then
    TARGET_USER="${SUDO_USER:-${USER}}"
    TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
    if [[ -z ${TARGET_HOME} ]]; then
        echo "Kullanıcı ev dizini bulunamadı: ${TARGET_USER}" >&2
        exit 1
    fi
    CONFIG_HOME="${XDG_CONFIG_HOME:-${TARGET_HOME}/.config}"
    rm -rf -- "${CONFIG_HOME}/aw2724dm-control"
    echo "Uygulama ve kullanıcı yapılandırması kaldırıldı."
else
    echo "Uygulama kaldırıldı. Kullanıcı yapılandırması korundu."
    echo "Onu da silmek için: ./uninstall.sh --purge"
fi
echo "i2c grubu ve paketler başka uygulamalarca kullanılabileceği için kaldırılmadı."
