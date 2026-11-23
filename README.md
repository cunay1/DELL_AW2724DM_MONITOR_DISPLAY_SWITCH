# AW2724DM Monitor Control

[Türkçe README](README_TR.md)

AW2724DM Monitor Control is a graphical monitor input switcher and display
settings manager developed for **Ubuntu 26.04 LTS with the GNOME X11/Xorg
desktop session**. It is designed for the Dell Alienware AW2724DM and other
monitors that support DDC/CI.

The application communicates with monitor hardware through `ddcutil`. It can
detect connected monitors and their supported input sources, switch between
DisplayPort and HDMI inputs, adjust brightness and contrast, and expose the same
operations through its GUI, command-line interface, GNOME keyboard shortcuts,
and system tray menu.

> This application intentionally targets X11/Xorg. The graphical interface does
> not run in a Wayland session and forces Qt to use the `xcb` backend.

## Features

- Automatic monitor discovery using `ddcutil detect`
- Automatic input-source discovery from VCP feature `0x60`
- Support for Dell Alienware AW2724DM and other DDC/CI monitors
- One-click switching between DisplayPort and HDMI inputs
- Toggle shortcuts between any two user-selected input ports
- Custom aliases such as “Home PC” and “Work Laptop”
- Brightness control through VCP `0x10`
- Contrast control through VCP `0x12`
- GNOME custom keyboard shortcut creation with `gsettings`
- X11 system tray integration
- CLI commands suitable for GNOME keyboard shortcuts and scripts
- Per-user configuration in `~/.config/aw2724dm-control/config.json`
- Automatic update checks through GitHub Releases
- SHA-256 and Ed25519 verification before an update is installed
- Ubuntu 26.04 GitHub Actions CI and signed Release workflow

## Requirements

- Ubuntu 26.04 LTS
- GNOME running in an X11/Xorg session
- A DDC/CI-compatible monitor
- DDC/CI enabled in the monitor's on-screen menu
- Internet access during installation
- `sudo` access for system package and I²C configuration

At the login screen, select your user, open the gear menu, and choose
**Ubuntu on Xorg**. Verify the session after logging in:

```bash
echo "$XDG_SESSION_TYPE"
```

The output must be `x11`.

## Installation

Clone the repository and run the installer:

```bash
git clone https://github.com/cunay1/DELL_AW2724DM_MONITOR_DISPLAY_SWITCH.git
cd DELL_AW2724DM_MONITOR_DISPLAY_SWITCH
chmod +x install.sh uninstall.sh
./install.sh
```

The installer:

1. Installs `ddcutil`, I²C tools, PyQt6 runtime dependencies, and X11 support
   packages.
2. Enables the `i2c-dev` kernel module.
3. Creates the `i2c` group if necessary and adds the installing user to it.
4. Installs an I²C udev permission rule.
5. Installs the application under `/opt/aw2724dm-control`.
6. Creates `/usr/local/bin/aw2724dm-control`.
7. Installs the desktop entry, icon, update helper, and update verification key.

### Important: log out after installation

Group membership changes do not affect the current desktop session. Fully log
out of GNOME and log back in using **Ubuntu on Xorg**. Reboot if necessary.

Verify access after starting a new session:

```bash
id -nG | tr ' ' '\n' | grep '^i2c$'
ddcutil detect
aw2724dm-control --list
```

## Running the application

Open **AW2724DM Monitor Control** from the GNOME application menu or run:

```bash
aw2724dm-control
```

The application scans connected monitors and reads their VCP capabilities in a
background worker, keeping the GUI responsive during DDC/CI operations.

### Input source controls

Detected inputs appear as buttons. Select an input to switch immediately. Input
names reported by the monitor can be replaced with custom aliases.

### Toggle shortcuts

Select two different inputs in the Quick Toggle section. The GUI toggle button
and the default `--toggle` CLI command use that saved pair.

The **Assign GNOME Shortcut** dialog also allows each shortcut to use its own
pair of DisplayPort or HDMI inputs. Press the desired key combination directly
in the shortcut field.

### Brightness and contrast

Brightness uses VCP feature `0x10`; contrast uses `0x12`. The new value is sent
when the slider is released.

### System tray

Closing the window hides the application in the X11 system tray. Inputs can be
switched directly from the tray menu. Choose **Quit** from the tray menu to stop
the application completely.

Ubuntu 26.04 provides AppIndicator support through the
`gnome-shell-ubuntu-extensions` package, which is installed automatically.

## Command-line interface

List monitors and detected input sources:

```bash
aw2724dm-control --list
```

Switch directly to an input:

```bash
aw2724dm-control --set-input 0x11
aw2724dm-control --display 2 --set-input 0x0f
```

Toggle the pair saved in the GUI:

```bash
aw2724dm-control --toggle
```

Toggle an explicit pair of inputs:

```bash
aw2724dm-control --display 1 --toggle 0x0f 0x11
```

Adjust brightness and contrast:

```bash
aw2724dm-control --brightness 70
aw2724dm-control --contrast 65
aw2724dm-control --display 1 --brightness 70 --contrast 65
```

Show all available options:

```bash
aw2724dm-control --help
```

Common MCCS input values include `0x0f` for DisplayPort 1, `0x10` for
DisplayPort 2, `0x11` for HDMI 1, and `0x12` for HDMI 2. Values vary by monitor;
always use `--list` to inspect the values reported by your hardware.

## GNOME keyboard shortcuts

### From the application

1. Select the target monitor.
2. Select **Assign GNOME Shortcut**.
3. Choose a direct input action or a two-input toggle action.
4. For a toggle action, select the two DisplayPort/HDMI inputs.
5. Focus the shortcut field and press the desired key combination.
6. Confirm the dialog.

The application adds the command under
`org.gnome.settings-daemon.plugins.media-keys` while preserving existing custom
shortcuts.

### From GNOME Settings

Open **Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts**
and use a command such as:

```bash
aw2724dm-control --display 1 --toggle 0x0f 0x11
```

or:

```bash
aw2724dm-control --display 1 --set-input 0x11
```

These commands work even when the GUI is not running.

## Secure automatic updates

The application checks the latest stable GitHub Release asynchronously, at most
once every six hours. Manual checks are available through the **Check for
Updates** button.

An update is installed only after all of the following checks pass:

1. The Release contains the expected versioned archive, SHA-256 file, and
   Ed25519 signature.
2. The archive matches the published SHA-256 digest.
3. The signature is valid for the public key installed at
   `/opt/aw2724dm-control/release-public-key.pem`.

The privileged installation step is never started when verification fails.

## Configuration

Settings are stored in:

```text
~/.config/aw2724dm-control/config.json
```

The file contains the selected monitor, aliases, toggle pairs, tray behavior,
and update-check timestamp. It is written atomically with `0600` permissions.

## Troubleshooting

### Permission denied or no monitor detected

```bash
groups
ls -l /dev/i2c-*
lsmod | grep i2c_dev
ddcutil environment
ddcutil detect
```

Confirm that the user belongs to the `i2c` group and that DDC/CI is enabled in
the monitor menu. Log out and back in after installation.

### Input Source VCP feature is missing

Inspect the raw monitor capabilities:

```bash
ddcutil capabilities --display 1
```

Some monitors support DDC/CI brightness controls but do not expose input source
switching through VCP `0x60`.

### The GUI reports an X11 error

```bash
echo "$XDG_SESSION_TYPE"
echo "$DISPLAY"
```

The first command must return `x11`; the second normally returns `:0` or `:1`.

## Tests

Run the hardware-independent parser, updater, and GUI smoke tests:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

The repository also runs the test suite on an Ubuntu 26.04 GitHub-hosted runner.

## Uninstallation

Remove the application while preserving user configuration:

```bash
./uninstall.sh
```

Remove the application and user configuration:

```bash
./uninstall.sh --purge
```

The `i2c` group and installed Ubuntu packages are intentionally preserved because
other DDC/I²C applications may use them.

## Security

Do not report vulnerabilities through public Issues. Follow the instructions in
[SECURITY.md](SECURITY.md) and use GitHub's private vulnerability reporting
form.

Hardware commands are executed without `shell=True`, CLI values are validated,
DDC operations use timeouts, GitHub Actions dependencies are pinned to immutable
commit SHAs, and Release archives are signed before publication.

## License

No license has been selected yet. Unless a license is added, copyright law
reserves all rights to the repository owner.
