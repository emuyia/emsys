#!/bin/bash

# ln -s /home/patch/repos/emsys/emsys.service ~/.config/systemd/user/emsys.service && systemctl --user daemon-reload && systemctl --user enable emsys && systemctl --user start emsys

~/Applications/pdnext/bin/pd ~/repos/emsys/em.sys.pd &
sleep 15
wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz
