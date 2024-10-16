#!/bin/bash

MOUNTPOINT=~/.mnt/patchbox_home
REMOTE=patch@patchbox.local:/home/patch/
LOGFILE=~/.mnt/mnt_patchbox.log

echo "$(date): Checking mount" >> $LOGFILE

if [ "$1" == "-u" ]; then
    echo "$(date): Unmounting $MOUNTPOINT" >> $LOGFILE
    fusermount -u "$MOUNTPOINT" >> $LOGFILE 2>&1
    exit 0
fi

if ! mountpoint -q "$MOUNTPOINT"; then
    echo "$(date): Mounting $REMOTE to $MOUNTPOINT" >> $LOGFILE
    sshfs -o reconnect $REMOTE $MOUNTPOINT >> $LOGFILE 2>&1
else
    echo "$(date): Already mounted" >> $LOGFILE
fi