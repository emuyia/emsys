#!/bin/bash

cd ~/repos/emsys || { echo "Directory not found"; exit 1; }

echo "Pulling latest changes from Git..."
git pull origin dev

# echo "Copying emsys.service to system directory..."
# sudo cp emsys.service /etc/systemd/system/emsys.service

# echo "Reloading systemd daemon..."
# sudo systemctl daemon-reload

# echo "Restarting emsys.service..."
# sudo systemctl restart emsys.service

# echo "Current status of emsys.service:"
# sudo journalctl -u emsys.service -f

sudo ./start.sh
