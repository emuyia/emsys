#!/bin/bash
# This script will notify that the system has booted using the Pisound's LEDs

. /usr/local/pisound/scripts/common/common.sh

# Flash the LEDs in a specific pattern to indicate the system has booted
for i in $(seq 1 5); do
    flash_leds 1  # Flash once
    sleep 0.2     # Short pause
done

log "System has booted!"
