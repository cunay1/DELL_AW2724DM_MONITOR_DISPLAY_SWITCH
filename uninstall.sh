#!/usr/bin/env bash
set -Eeuo pipefail

COMMAND_LINK="/usr/local/bin/aw2724dm-control"
DESKTOP_FILE="/usr/share/applications/aw2724dm-control.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/aw2724dm-control.svg"

INSTALL_DIR="${AW2724DM_INSTALL_DIR:-/opt/aw2724dm-control}"
if [[ -L ${COMMAND_LINK} ]]; then
    INSTALLED_LAUNCHER="$(readlink -f -- "${COMMAND_LINK}")"
    if [[ $(basename -- "${INSTALLED_LAUNCHER}") == aw2724dm-control ]]; then
        INSTALL_DIR="$(dirname -- "${INSTALLED_LAUNCHER}")"
    fi
fi
INSTALL_DIR="$(realpath -m -- "${INSTALL_DIR}")"
case "${INSTALL_DIR}" in
    /|/opt|/usr|/usr/local|/home|/root|/var|/etc|/bin|/sbin|/lib|/lib32|/lib64|/boot|/dev|/proc|/sys|/run|/tmp|/etc/*|/bin/*|/sbin/*|/lib/*|/lib32/*|/lib64/*|/boot/*|/dev/*|/proc/*|/sys/*|/run/*|/tmp/*)
        echo "Güvenli olmayan kaldırma hedefi reddedildi: ${INSTALL_DIR}" >&2
        exit 2
        ;;
esac
if [[ $(dirname -- "${INSTALL_DIR}") == / ]]; then
    echo "Güvenli olmayan sığ kaldırma hedefi reddedildi: ${INSTALL_DIR}" >&2
    exit 2
fi

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
    STATE_HOME="${XDG_STATE_HOME:-${TARGET_HOME}/.local/state}"
    rm -rf -- "${CONFIG_HOME}/aw2724dm-control"
    rm -rf -- "${STATE_HOME}/aw2724dm-control"
    echo "Uygulama, kullanıcı yapılandırması ve loglar kaldırıldı."
else
    echo "Uygulama kaldırıldı. Kullanıcı yapılandırması korundu."
    echo "Onu da silmek için: ./uninstall.sh --purge"
fi
echo "i2c grubu ve paketler başka uygulamalarca kullanılabileceği için kaldırılmadı."
