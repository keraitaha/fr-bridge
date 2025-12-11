#!/bin/bash

# Linux Run Script

# 1. Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 could not be found. Please install python3."
    exit 1
fi

echo "Found Python 3"

# 2. Install Dependencies
echo "Installing/Checking dependencies..."
sudo apt update
sudo apt install -y python3-requests python3-schedule

# 3. Setup Database if not exists
if [ ! -f "mock.db" ]; then
    echo "Database not found. Running setup..."
    python3 setup_mock_db.py
else
    echo "Database found."
fi

# 4. Run Application
echo "Starting Bridge Application..."
python3 bridge.py "$@"
