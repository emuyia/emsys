# emsys
A bespoke live music companion to MCL built in Pd for Pisound.

## Setup
> A niche hardware configuration is required. Not made for general use.

Begin by cloning the repository:
```
git clone https://github.com/emuyia/emsys.git
cd emsys
```

#### em_clock.py & em_midisetup.py
> Note: em_midisetup is intended for Pisound (Linux) only.

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

> Note: For Windows, you must additionally install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) and create a MIDI loopback port named `em_clock`.

You are now able to run em_clock or em_midisetup directly with `python serv/em_clock.py` and `python serv/em_midisetup.py`.

#### systemd services

If you intend to run emsys from boot on a Linux device, it is recommended to allow both scripts to run automatically via systemd:
1. First edit the `.service` files in `serv` so that `WorkingDirectory` and `ExecStart` have correct paths.
2. Then run:
```
# Create symlinks
ln -s serv/em_midisetup.service ~/.config/systemd/user/em_midisetup.service
ln -s serv/em_clock.service ~/.config/systemd/user/em_clock.service

# Reload systemctl, then enable & start services
systemctl --user daemon-reload
systemctl --user enable em_clock
systemctl --user start em_clock
systemctl --user enable em_midisetup
systemctl --user start em_midisetup
```

#### boot.conf
`boot.conf` contains settings necessary for emsys to run.
1. Rename or copy `serv/boot.conf.example` to `serv/boot.conf`.
2. Rename or copy `sets/init.mset.example` to `sets/init.mset`.
3. Open boot.conf in a text editor & set `path` to the emsys directory.

Optional: Change `env.defaults.dev` to `1` if you intend to use emsys with plugdata. This tells emsys to assume that all connected MIDI devices are on Port 1 (this can be adjusted later).

#### Running emsys
`main.pd` is the entry point for emsys. It can be run in plugdata or Pure Data on macOS and Linux, however it is primarily intended for a headless Linux system running Pure Data in CLI, such as a Raspberry Pi.

`serv/em_sys.sh` should be used to run emsys in CLI. Otherwise, `main.pd` can be opened directly.

If `em_midisetup.py` is not in use, you will need to configure MIDI devices manually in plugdata or Pd, and then reopen `main.pd`.

> Note: `serv/em_sys.sh` can also be targeted as a function for the pisound "button" by creating a symlink here: `sudo ln -s serv/em_sys.sh /usr/local/pisound/scripts/pisound-btn/em_sys.sh`, and then assigning it within Patchbox OS.

## Usage
WIP
