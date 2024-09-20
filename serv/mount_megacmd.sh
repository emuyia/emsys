#!/bin/bash

MOUNTPOINT=~/.mnt/patchbox_megacmd
REMOTE=patch@patchbox.local:/media/patch/
LOGFILE=~/.mnt/mnt_patchbox.log
DEVICE=/dev/sda1

echo "$(date): Checking mount" >> $LOGFILE

if [ "$1" == "-u" ]; then
    echo "$(date): Unmounting $MOUNTPOINT and device on remote" >> $LOGFILE
    ssh patch@patchbox.local "udevil unmount $DEVICE" >> $LOGFILE 2>&1
    fusermount -u "$MOUNTPOINT" >> $LOGFILE 2>&1
    exit 0
fi

if ! mountpoint -q "$MOUNTPOINT"; then
    echo "$(date): Mounting $REMOTE to $MOUNTPOINT" >> $LOGFILE
    sshfs -o reconnect $REMOTE $MOUNTPOINT >> $LOGFILE 2>&1
else
    echo "$(date): Already mounted" >> $LOGFILE
fi

# SSH and mount the device on the remote system
ssh patch@patchbox.local "udevil mount $DEVICE" >> $LOGFILE 2>&1