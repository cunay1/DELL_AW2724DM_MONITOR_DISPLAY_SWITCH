from __future__ import annotations

import os
import json
import sys
import time
from datetime import datetime
from pathlib import Path


def process_start_time(pid: int) -> str | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    closing = stat.rfind(") ")
    if closing < 0:
        return None
    fields = stat[closing + 2 :].split()
    return fields[19] if len(fields) > 19 else None


def process_matches(pid: int, expected_start_time: str) -> bool:
    return process_start_time(pid) == expected_start_time


def descendant_process_identities(parent_pid: int) -> list[tuple[int, str]]:
    parent_by_pid: dict[int, int] = {}
    start_by_pid: dict[int, str] = {}
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            pid = int(entry.name)
            stat = (entry / "stat").read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        closing = stat.rfind(") ")
        fields = stat[closing + 2 :].split() if closing >= 0 else []
        if len(fields) <= 19:
            continue
        try:
            parent_by_pid[pid] = int(fields[1])
        except ValueError:
            continue
        start_by_pid[pid] = fields[19]
    descendants: list[tuple[int, str]] = []
    pending = [parent_pid]
    while pending:
        current = pending.pop()
        children = [pid for pid, ppid in parent_by_pid.items() if ppid == current]
        for child in children:
            descendants.append((child, start_by_pid[child]))
            pending.append(child)
    return descendants


def append_abnormal_shutdown_log(path: Path, process_ids: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        handle.write(
            f"{timestamp} ERROR aw2724dm_control.shutdown_monitor "
            f"Application-related process(es) {process_ids} remained alive after shutdown request.\n"
        )
    os.chmod(path, 0o600)


def main() -> int:
    if len(sys.argv) != 6:
        return 2
    try:
        pid = int(sys.argv[1])
    except ValueError:
        return 2
    expected_start_time, log_file, language = sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    try:
        child_identities = [(int(pid), str(start)) for pid, start in json.loads(sys.argv[5])]
    except (TypeError, ValueError, json.JSONDecodeError):
        return 2
    time.sleep(5)
    remaining = []
    if process_matches(pid, expected_start_time):
        remaining.append(pid)
    remaining.extend(
        child_pid
        for child_pid, child_start in child_identities
        if process_matches(child_pid, child_start)
    )
    if not remaining:
        return 0
    append_abnormal_shutdown_log(log_file, remaining)

    from PyQt6.QtWidgets import QApplication, QMessageBox

    application = QApplication([])
    if language == "tr":
        title = "Uygulama Düzgün Kapanmadı"
        message = (
            "AW2724DM Monitor Control kapatıldıktan sonra işlem çalışmaya "
            "devam ediyor. Ayrıntılar log dosyasına kaydedildi."
        )
    else:
        title = "Application Did Not Exit Cleanly"
        message = (
            "The AW2724DM Monitor Control process is still running after shutdown. "
            "Details were written to the log file."
        )
    QMessageBox.warning(None, title, message)
    application.quit()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
