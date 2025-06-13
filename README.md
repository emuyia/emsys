<div align="center">
    <img src="resources/banner.webp" height="80">
    <p>A bespoke live music companion to MCL built in Pd for Pisound.</p>
</div>

## Setup
> A niche hardware configuration is required. Not made for general use.

Begin by cloning the repository:
```
git clone https://github.com/emuyia/emsys.git
cd emsys
```

#### em_clock.py, em_midisetup.py & em_pd_controller.py
> Note: em_midisetup & em_pd_controller are intended for Pisound (Linux) only.

- `em_clock.py` creates the central realtime MIDI clock.
- `em_midisetup.py` maintains all necessary virtual MIDI connections.
- `em_pd_controller.py` starts the emsys Pd patch in CLI mode, and allows management the patch via a MiniLab 3 MIDI controller (Shift + Tap + Yes/No to start or stop the patch, at any time).

Set up the Python environment:
```
 # Set up venv
python -m venv .venv

# Activate venv
source .venv/bin/activate  # Linux & macOS
source .venv/Scripts/Activate  # Windows (Bash)
.\.venv\Scripts\Activate.ps1  # Windows (PowerShell)

# Install requirements
pip install -r requirements.txt
```

> Note: For Windows, you must additionally install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) and create a MIDI loopback port named `em_clock`. Virtual MIDI routing can be performed with [MIDI-OX](http://www.midiox.com/).

You are now able to run em_clock, em_midisetup or em_pd_controller directly with `python serv/em_clock.py`, `python serv/em_midisetup.py` and `python serv/em_pd_controller.py`.

> Note: If you're unable to get `em_clock` running, you can instead use the internal clock contained in the patch, which uses `[else/midi.clock]`. You can turn it on within `main.pd` later. Keep in mind that this clock is unstable, and is therefore not recommended for production.

#### systemd services

If you intend to run emsys from boot on a Linux device, it is recommended to allow all scripts to run automatically via systemd:
1. First edit the `.service` files in `serv` so that `WorkingDirectory` and `ExecStart` have correct paths.
2. Then run:
```
# Reload systemctl, then enable services
systemctl --user daemon-reload
systemctl --user enable serv/em_clock.service
systemctl --user enable serv/em_midisetup.service

# For the Pd controller we need broader permissions (e.g., for disk writes):
sudo systemctl daemon-reload
sudo systemctl enable serv/em_pd_controller.service
```

#### boot.conf
`boot.conf` contains settings necessary for emsys to run.
1. Rename or copy `serv/boot.conf.example` to `serv/boot.conf`.
2. Rename or copy `sets/init.mset.example` to `sets/init.mset`.

Optional: Change `env.defaults.dev` to `1` if you intend to use emsys with plugdata. This tells emsys to assume that all connected MIDI devices are on Port 1 (this can be adjusted later).

#### Running emsys
`main.pd` is the entry point for emsys. It can be run in plugdata or Pure Data on macOS and Linux, however it is primarily intended for a headless Linux system running Pure Data in CLI, such as a Raspberry Pi.

`serv/em_pd_controller.py` should be used to run emsys on boot using the corresponding systemd service, `serv/em_pd_controller.service`. Otherwise, `main.pd` can be opened directly.

If `em_midisetup.py` is not in use, you will need to configure MIDI devices manually in plugdata or Pd, and then reopen `main.pd`.

> Note: `main.pd` contains a rudimentary emulation of the ML3 controls & screens. It can be used for most functions but should not be relied on in production.

## Usage
#### Managing emsys state
- On boot, emsys will launch. It can be managed with the following inputs on the MiniLab:
    - Shift+Tap+YES: Start patch
    - Shift+Tap+NO: Stop patch
    - Shift+Tap+Reload: Reboot system

WIP
