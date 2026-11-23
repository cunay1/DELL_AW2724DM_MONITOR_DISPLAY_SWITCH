from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

from .i18n import tr


class DDCError(RuntimeError):
    """ddcutil çalıştırma veya çıktı çözümleme hatası."""


@dataclass(slots=True)
class InputSource:
    code: int
    name: str


@dataclass(slots=True)
class Monitor:
    display: int
    model: str = ""
    manufacturer: str = ""
    serial: str = ""
    bus: str = ""
    connector: str = ""
    inputs: list[InputSource] = field(default_factory=list)

    @property
    def title(self) -> str:
        details = self.model or tr("unknown_monitor")
        if self.connector:
            details += f" — {self.connector}"
        return tr("display_title", display=self.display, details=details)


class DDCUtil:
    FALLBACK_INPUT_NAMES = {
        0x0F: "DisplayPort-1",
        0x10: "DisplayPort-2",
        0x11: "HDMI-1",
        0x12: "HDMI-2",
    }

    def __init__(self, executable: str = "ddcutil", timeout: int = 20) -> None:
        self.executable = executable
        self.timeout = timeout

    def ensure_available(self) -> None:
        if shutil.which(self.executable) is None:
            raise DDCError(tr("ddcutil_missing"))

    def run(self, *arguments: str, timeout: int | None = None) -> str:
        self.ensure_available()
        command = [self.executable, "--noverify", *arguments]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.timeout,
                env=None,
            )
        except subprocess.TimeoutExpired as exc:
            raise DDCError(tr("ddcutil_timeout", seconds=timeout or self.timeout)) from exc
        except OSError as exc:
            raise DDCError(tr("ddcutil_run_failed", error=exc)) from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            raise DDCError(message or tr("ddcutil_exit", code=result.returncode))
        return result.stdout

    @staticmethod
    def parse_detect(output: str) -> list[Monitor]:
        monitors: list[Monitor] = []
        current: Monitor | None = None
        for raw_line in output.splitlines():
            line = raw_line.strip()
            match = re.match(r"Display\s+(\d+)", line, re.IGNORECASE)
            if match:
                current = Monitor(display=int(match.group(1)))
                monitors.append(current)
                continue
            if current is None:
                continue
            fields = {
                "I2C bus:": "bus",
                "DRM connector:": "connector",
                "Mfg id:": "manufacturer",
                "Model:": "model",
                "Serial number:": "serial",
            }
            for prefix, attribute in fields.items():
                if line.lower().startswith(prefix.lower()):
                    setattr(current, attribute, line.split(":", 1)[1].strip())
                    break
        return monitors

    @staticmethod
    def parse_inputs(output: str) -> list[InputSource]:
        lines = output.splitlines()
        in_feature = False
        inputs: dict[int, str] = {}
        for raw_line in lines:
            line = raw_line.strip()
            feature = re.match(r"Feature:\s*([0-9a-fA-F]{2})\b", line)
            if feature:
                in_feature = feature.group(1).lower() == "60"
                continue
            if not in_feature:
                continue
            # ddcutil sürümleri hem "0f: DisplayPort-1" hem "0x0f: ..." yazabilir.
            value = re.match(r"(?:0x)?([0-9a-fA-F]{2})\s*:\s*(.+?)\s*$", line)
            if value:
                code = int(value.group(1), 16)
                name = value.group(2).strip()
                if name.casefold().startswith("unrecognized"):
                    name = DDCUtil.FALLBACK_INPUT_NAMES.get(code, tr("unknown_input", code=code))
                inputs[code] = name
                continue
            # Bazı MCCS çıktılarında değerler tek satırda sadece hex olarak verilir.
            if line.lower().startswith("values:"):
                for token in re.findall(r"(?:0x)?([0-9a-fA-F]{2})\b", line.split(":", 1)[1]):
                    code = int(token, 16)
                    inputs.setdefault(code, tr("unknown_input", code=code))
        return [InputSource(code, name) for code, name in sorted(inputs.items())]

    @staticmethod
    def parse_current_value(output: str) -> int:
        match = re.search(r"current value\s*=\s*(0x[0-9a-fA-F]+|\d+)", output, re.IGNORECASE)
        if match:
            return int(match.group(1), 0)
        match = re.search(r"sl=0x([0-9a-fA-F]+)", output, re.IGNORECASE)
        if match:
            return int(match.group(1), 16)
        raise DDCError(tr("ddc_value_parse"))

    def detect(self) -> list[Monitor]:
        monitors = self.parse_detect(self.run("detect", timeout=30))
        for monitor in monitors:
            try:
                capabilities = self.run("capabilities", "--display", str(monitor.display), timeout=30)
                monitor.inputs = self.parse_inputs(capabilities)
            except DDCError:
                monitor.inputs = []
        return monitors

    def get_vcp(self, display: int, feature: int) -> int:
        output = self.run("getvcp", f"0x{feature:02x}", "--display", str(display))
        return self.parse_current_value(output)

    def set_vcp(self, display: int, feature: int, value: int) -> None:
        self.run(
            "setvcp",
            f"0x{feature:02x}",
            f"0x{value:02x}" if feature == 0x60 else str(value),
            "--display",
            str(display),
        )

    def set_input(self, display: int, value: int) -> None:
        self.set_vcp(display, 0x60, value)

    def toggle(self, display: int, first: int, second: int) -> int:
        current = self.get_vcp(display, 0x60)
        target = second if current == first else first
        self.set_input(display, target)
        return target
