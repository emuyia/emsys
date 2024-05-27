#!/bin/bash

cd ~/repos/emsys || { echo "Directory not found"; exit 1; }

echo "Pulling latest changes from Git..."
git pull origin dev

echo "Restarting emsys.service..."
sudo systemctl restart emsys.service

echo "Current status of emsys.service:"
sudo systemctl status emsys.service
