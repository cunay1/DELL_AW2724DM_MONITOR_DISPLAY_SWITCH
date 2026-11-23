from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import ConfigStore
from .ddc import DDCError, DDCUtil


def integer(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Geçersiz sayı: {value}") from exc


def percentage(value: str) -> int:
    parsed = integer(value)
    if not 0 <= parsed <= 100:
        raise argparse.ArgumentTypeError("Değer 0 ile 100 arasında olmalıdır.")
    return parsed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="aw2724dm-control",
        description="DDC/CI monitör giriş kaynağı ve görüntü ayarı yöneticisi",
    )
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    result.add_argument("--display", type=int, help="ddcutil ekran numarası (varsayılan: yapılandırmadaki ekran)")
    result.add_argument("--list", action="store_true", help="Monitörleri ve giriş kaynaklarını listele")
    actions = result.add_argument_group("CLI işlemleri")
    actions.add_argument("--set-input", type=integer, metavar="KOD", help="VCP 0x60 giriş kodunu ayarla")
    actions.add_argument(
        "--toggle",
        nargs="*",
        type=integer,
        metavar="KOD",
        help="İki giriş arasında geç; isteğe bağlı olarak iki giriş kodu verilebilir",
    )
    actions.add_argument("--brightness", type=percentage, metavar="0-100", help="Parlaklığı ayarla")
    actions.add_argument("--contrast", type=percentage, metavar="0-100", help="Kontrastı ayarla")
    return result


def run_cli(args: argparse.Namespace, config: ConfigStore, ddc: DDCUtil) -> int:
    display = args.display or int(config.data.get("selected_display", 1))
    try:
        if args.list:
            monitors = ddc.detect()
            if not monitors:
                print("DDC/CI monitörü bulunamadı.", file=sys.stderr)
                return 1
            for monitor in monitors:
                print(monitor.title)
                for source in monitor.inputs:
                    alias = config.aliases(monitor.display).get(f"0x{source.code:02x}")
                    suffix = f" ({alias})" if alias else ""
                    print(f"  0x{source.code:02x}  {source.name}{suffix}")
        if args.set_input is not None:
            if not 0 <= args.set_input <= 0xFF:
                raise DDCError("Giriş kodu 0x00 ile 0xff arasında olmalıdır.")
            ddc.set_input(display, args.set_input)
            print(f"Ekran {display} girişi 0x{args.set_input:02x} olarak ayarlandı.")
        if args.toggle is not None:
            if len(args.toggle) == 0:
                pair = config.toggle_inputs(display)
                if pair is None:
                    raise DDCError("Geçiş girişleri henüz ayarlanmamış. Önce GUI'den iki giriş seçin.")
            elif len(args.toggle) == 2:
                pair = int(args.toggle[0]), int(args.toggle[1])
            else:
                raise DDCError("--toggle sıfır veya tam iki giriş kodu kabul eder.")
            if pair[0] == pair[1] or any(code < 0 or code > 0xFF for code in pair):
                raise DDCError("Geçiş için 0x00–0xff aralığında iki farklı giriş kodu gerekir.")
            target = ddc.toggle(display, pair[0], pair[1])
            print(f"Ekran {display} girişi 0x{target:02x} olarak ayarlandı.")
        if args.brightness is not None:
            ddc.set_vcp(display, 0x10, args.brightness)
            print(f"Ekran {display} parlaklığı %{args.brightness} olarak ayarlandı.")
        if args.contrast is not None:
            ddc.set_vcp(display, 0x12, args.contrast)
            print(f"Ekran {display} kontrastı %{args.contrast} olarak ayarlandı.")
    except DDCError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1
    return 0


def run_gui(config: ConfigStore, ddc: DDCUtil) -> int:
    from PyQt6.QtWidgets import QApplication

    from .gui import create_window

    application = QApplication(sys.argv)
    application.setApplicationName("AW2724DM Monitor Control")
    application.setDesktopFileName("aw2724dm-control")
    application.setQuitOnLastWindowClosed(False)
    window = create_window(config, ddc)
    window.show()
    return application.exec()


def main() -> int:
    args = parser().parse_args()
    config = ConfigStore()
    ddc = DDCUtil()
    cli_requested = any(
        (
            args.list,
            args.set_input is not None,
            args.toggle is not None,
            args.brightness is not None,
            args.contrast is not None,
        )
    )
    return run_cli(args, config, ddc) if cli_requested else run_gui(config, ddc)


if __name__ == "__main__":
    raise SystemExit(main())
