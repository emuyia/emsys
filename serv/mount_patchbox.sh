#!/bin/bash

MOUNTPOINT=~/.mnt/patchbox_home
REMOTE=patch@patchbox.local:/home/patch/
LOGFILE=~/.mnt_patchbox.log

echo "$(date): Checking mount" >> $LOGFILE

if ! mountpoint -q "$MOUNTPOINT"; then
    echo "$(date): Mounting $REMOTE to $MOUNTPOINT" >> $LOGFILE
    sshfs $REMOTE $MOUNTPOINT >> $LOGFILE 2>&1
else
    echo "$(date): Already mounted" >> $LOGFILE
fi
