Simple Server for DAO CO2 Observation Units
==================================================

This is a simple HTTP server for our CO2 Observation Units.
It is written in Python with Flask.

Running the server
--------------------------------------------------

### Installation

The code can be installed anywhere and run from its own directory.
It does need access to the Python Flask library.

### Virtualenv setup

```bash
# Create a virtual environment
python3 -m virtualenv --python=python3 .venv

# Activate the virtal environment
source .venv/bin/activate

# Install Python's development libs
# (required by uwsgi, which needs to compile C components)
sudo apt install python3-dev

# Install required packages (flask, flast-restful, uwsgi)
pip install -r requirements.txt
```

### Testing: Run in Flask's development container

```bash
# Activate virtual env if you haven't already
source .venv/bin/activate

cd src/
python server.py --port 8080
```

### Testing: Run in uWSGI container

```bash
# Activate virtual env if you haven't already
source .venv/bin/activate

cd src/
uwsgi --socket 0.0.0.0:8080 --protocol=http -w server:app
```

### Production: Run in uWSGI container with options in .ini file

```bash
# Copy and customize example server.ini
cp src/server.ini.example

# Start server via script
./scripts/start-server.sh

# Script just does the following
# ----------------------------------------
# source .venv/bin/activate
# cd src/
# uwsgi --ini server.ini
```

### Production: Install as systemd service

```bash
# Copy and customize example systemd service file
cp co2unit-server.service.example co2unit-server.service

# Copy to systemd directory
sudo cp co2unit-server.service /etc/systemd/system/

# Start service
sudo systemctl start co2unit-server

# Set service to start on boot
sudo systemctl enable co2unit-server

# See status
systemctl status co2unit-server

# Follow log
journalctl -fu co2unit-server.service

# Follow log of just co2unit-related requests
journalctl -fu co2unit-server.service | grep co2unit
```
