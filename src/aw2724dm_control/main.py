from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigStore
from .ddc import DDCError, DDCUtil
from .i18n import set_language, tr
from .logging_config import get_logger, setup_logging


logger = get_logger("main")


def integer(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(tr("invalid_number", value=value)) from exc


def percentage(value: str) -> int:
    parsed = integer(value)
    if not 0 <= parsed <= 100:
        raise argparse.ArgumentTypeError(tr("percentage_range"))
    return parsed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="aw2724dm-control",
        description=tr("cli_description"),
    )
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    result.add_argument("--display", type=int, help=tr("display_help"))
    result.add_argument("--list", action="store_true", help=tr("list_help"))
    actions = result.add_argument_group(tr("cli_actions"))
    actions.add_argument("--set-input", type=integer, metavar="CODE", help=tr("set_input_help"))
    actions.add_argument(
        "--toggle",
        nargs="*",
        type=integer,
        metavar="CODE",
        help=tr("toggle_help"),
    )
    actions.add_argument("--brightness", type=percentage, metavar="0-100", help=tr("brightness_help"))
    actions.add_argument("--contrast", type=percentage, metavar="0-100", help=tr("contrast_help"))
    return result


def run_cli(args: argparse.Namespace, config: ConfigStore, ddc: DDCUtil) -> int:
    display = args.display or int(config.data.get("selected_display", 1))
    try:
        if args.list:
            monitors = ddc.detect()
            if not monitors:
                print(tr("no_ddc_monitor"), file=sys.stderr)
                return 1
            for monitor in monitors:
                print(monitor.title)
                for source in monitor.inputs:
                    alias = config.aliases(monitor.display).get(f"0x{source.code:02x}")
                    suffix = f" ({alias})" if alias else ""
                    print(f"  0x{source.code:02x}  {source.name}{suffix}")
        if args.set_input is not None:
            if not 0 <= args.set_input <= 0xFF:
                raise DDCError(tr("input_range"))
            ddc.set_input(display, args.set_input)
            print(tr("input_set", display=display, code=args.set_input))
        if args.toggle is not None:
            if len(args.toggle) == 0:
                pair = config.toggle_inputs(display)
                if pair is None:
                    raise DDCError(tr("toggle_not_configured"))
            elif len(args.toggle) == 2:
                pair = int(args.toggle[0]), int(args.toggle[1])
            else:
                raise DDCError(tr("toggle_argument_count"))
            if pair[0] == pair[1] or any(code < 0 or code > 0xFF for code in pair):
                raise DDCError(tr("toggle_pair_invalid"))
            target = ddc.toggle(display, pair[0], pair[1])
            print(tr("input_set", display=display, code=target))
        if args.brightness is not None:
            ddc.set_vcp(display, 0x10, args.brightness)
            print(tr("brightness_set", display=display, value=args.brightness))
        if args.contrast is not None:
            ddc.set_vcp(display, 0x12, args.contrast)
            print(tr("contrast_set", display=display, value=args.contrast))
    except DDCError as exc:
        print(tr("error_prefix", message=exc), file=sys.stderr)
        return 1
    return 0


def run_gui(config: ConfigStore, ddc: DDCUtil) -> int:
    from PyQt6.QtCore import QLockFile, QProcess, QStandardPaths
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from .gui import create_window
    from .styles import apply_application_style

    application = QApplication(sys.argv)
    application.setApplicationName("AW2724DM Monitor Control")
    application.setDesktopFileName("aw2724dm-control")
    application.setQuitOnLastWindowClosed(False)
    apply_application_style(application)
    runtime_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    lock_directory = Path(runtime_path) if runtime_path else Path.home() / ".cache"
    lock_directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_directory / "aw2724dm-control.lock"))
    if not lock.tryLock(100):
        if not lock.removeStaleLockFile() or not lock.tryLock(100):
            logger.warning("A second GUI instance was rejected")
            QMessageBox.information(
                None,
                tr("already_running_title"),
                tr("already_running"),
            )
            return 3
    window = create_window(config, ddc)
    window.show()
    exit_code = application.exec()
    restart_requested = application.property("restart_requested") is True
    lock.unlock()
    if restart_requested:
        program = "/usr/local/bin/aw2724dm-control"
        arguments: list[str] = []
        if not Path(program).exists():
            program = sys.executable
            arguments = ["-m", "aw2724dm_control"]
        started, process_id = QProcess.startDetached(program, arguments)
        if started:
            logger.info("Restarted application as process %s", process_id)
        else:
            logger.error("Automatic restart failed: %s %s", program, arguments)
            QMessageBox.critical(None, tr("operation_error"), tr("restart_failed"))
            return 4
    return exit_code


def main() -> int:
    log_path = setup_logging()
    logger.info("Starting AW2724DM Monitor Control %s; log=%s", __version__, log_path)
    config = ConfigStore()
    set_language(config.data.get("language", "en"))
    args = parser().parse_args()
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
    exit_code = run_cli(args, config, ddc) if cli_requested else run_gui(config, ddc)
    logger.info("Application exited with code %s", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
