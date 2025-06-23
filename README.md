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
- `em_pd_controller.py` allows for managing apps (such as emsys) using the MiniLab 3 MIDI controller as an interface.

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
sudo systemctl daemon-reload
sudo systemctl enable serv/em_pd_controller.service serv/em_clock.service serv/em_midisetup.service
sudo systemctl start em_pd_controller em_clock em_midisetup
```

#### boot.conf
`boot.conf` contains settings necessary for emsys to run.
1. Rename or copy `serv/boot.conf.example` to `serv/boot.conf`.
2. Rename or copy `sets/init.mset.example` to `sets/init.mset`.

Optional: Changing `env.defaults.dev` to `1` tells emsys to assume that all connected MIDI devices are on Port 1 (for compatibility with some versions of plugdata).

#### Running emsys
`main.pd` is the entry point for emsys. It is primarily intended for a headless Linux system running Pure Data in CLI, such as a Raspberry Pi, but can be run on any OS (provided you can perform virtual MIDI routing).

`serv/em_pd_controller.py` should be used to manage emsys on boot using the corresponding systemd service, `serv/em_pd_controller.service`. Otherwise, `main.pd` can be opened directly.

If `em_midisetup.py` is not in use, you will need to configure MIDI devices manually in plugdata or Pd, and then reopen `main.pd`.

> Note: `main.pd` contains a rudimentary emulation of the ML3 controls & screens. It can be used for most functions but should not be relied on in production.

## Usage (WIP)
#### Managing emsys state
- On boot, em_pd_controller will launch. It can be used to boot available apps (emsys, embliss) with the following inputs on the MiniLab:
    - Shift+Tap+YES: Start emsys
    - Shift+Tap+Pad7: Start embliss
    - Shift+Tap+NO: Stop all apps
    - Shift+Tap+Reload: Reboot system
- There are additional Pisound button controls for managing system state:
    - Hold 1s: Reboot system
    - Hold 3s: Shutdown system
