from __future__ import annotations

import unittest

from aw2724dm_control.ddc import DDCError, DDCUtil
from aw2724dm_control.main import parser


DETECT_OUTPUT = """
Display 1
   I2C bus:  /dev/i2c-7
   DRM connector:           card1-DP-1
   EDID synopsis:
      Mfg id:               DEL
      Model:                AW2724DM
      Serial number:        ABC123
Display 2
   I2C bus:  /dev/i2c-8
   DRM connector:           card1-HDMI-A-1
   EDID synopsis:
      Mfg id:               ACI
      Model:                Example Display
"""

CAPABILITIES_OUTPUT = """
VCP Features:
   Feature: 10 (Brightness)
   Feature: 60 (Input Source)
      Values:
         0f: DisplayPort-1
         11: HDMI-1
         12: HDMI-2
   Feature: 62 (Audio speaker volume)
"""

UNRECOGNIZED_DISPLAYPORT_OUTPUT = """
VCP Features:
   Feature: 60 (Input Source)
      Values:
         0f: DisplayPort-1
         10: Unrecognized value
         11: HDMI-1
"""


class DDCParserTests(unittest.TestCase):
    def test_detect_parser_reads_multiple_monitors(self) -> None:
        monitors = DDCUtil.parse_detect(DETECT_OUTPUT)
        self.assertEqual(len(monitors), 2)
        self.assertEqual(monitors[0].display, 1)
        self.assertEqual(monitors[0].model, "AW2724DM")
        self.assertEqual(monitors[0].connector, "card1-DP-1")
        self.assertEqual(monitors[1].bus, "/dev/i2c-8")

    def test_capabilities_parser_reads_only_input_feature(self) -> None:
        inputs = DDCUtil.parse_inputs(CAPABILITIES_OUTPUT)
        self.assertEqual([(item.code, item.name) for item in inputs], [
            (0x0F, "DisplayPort-1"),
            (0x11, "HDMI-1"),
            (0x12, "HDMI-2"),
        ])

    def test_unrecognized_input_10_uses_displayport_2_name(self) -> None:
        inputs = DDCUtil.parse_inputs(UNRECOGNIZED_DISPLAYPORT_OUTPUT)
        self.assertEqual(inputs[1].code, 0x10)
        self.assertEqual(inputs[1].name, "DisplayPort-2")

    def test_current_value_supports_decimal_and_hex(self) -> None:
        self.assertEqual(DDCUtil.parse_current_value("current value = 75, max value = 100"), 75)
        self.assertEqual(DDCUtil.parse_current_value("current value = 0x11"), 0x11)
        self.assertEqual(DDCUtil.parse_current_value("VCP 60 C 0x11 sl=0x11"), 0x11)

    def test_current_value_rejects_unknown_output(self) -> None:
        with self.assertRaises(DDCError):
            DDCUtil.parse_current_value("unsupported output")

    def test_toggle_cli_accepts_explicit_input_pair(self) -> None:
        arguments = parser().parse_args(["--display", "1", "--toggle", "0x0f", "0x11"])
        self.assertEqual(arguments.toggle, [0x0F, 0x11])


if __name__ == "__main__":
    unittest.main()
