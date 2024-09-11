#!/bin/bash
# Set up environment
source ~/.bashrc
export JACK_PROMISCUOUS_SERVER=jack
export DISPLAY=:0

# Start Pd
/home/patch/Applications/pdnext/bin/pd -jack -rt -nogui /home/patch/repos/emsys/main.pd
#/home/patch/Applications/pdnext/bin/pd -jack -rt -nogui /home/patch/repos/emsys/dummy.pd
