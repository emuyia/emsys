#!/bin/bash

# Check if the number of arguments is correct
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <command>"
    exit 1
fi

# Assign the argument to a variable
ACTION=$1

# Define the commands based on the argument
case $ACTION in
    reboot)
        COMMAND="sudo reboot"
        ;;
    reopen)
        COMMAND="killall pd || true && sleep 1 && export DISPLAY=:0.0 && ~/repos/emsys/emsys.sh &"
        ;;
    *)
        echo "Invalid command: $ACTION"
        exit 1
        ;;
esac

# Execute the command via SSH on the remote host
ssh patch@patchbox.local "$COMMAND"
