Simple Server for DAO CO2 Observation Units
==================================================

This is Python code for a backend server for a
CO2 sensor, or "Observation Unit",
developed at UiT The Arctic University of Norway
as part of the Distributed Arctic Observatory project.
These Observation Units are described in the paper:

Murphy et al.
"Experiences Building and Deploying
 Wireless Sensor Nodes for the Arctic Tundra,"
in The 21st IEEE/ACM International Symposium on
   Cluster, Cloud and Internet Computing (CCGrid 2021).
Melbourne Australia, May 2021.

The CO2 Observation Units are based on a FiPy microcontroller.
They push data via LTE CAT-M1 to a server in the lab.

This repository includes the server code,
plus scripts to import the data into a database and generate plots.
The server is a bare-bones HTTP server, written in Python with Flask.

Repositories and Documentation Associated with this Project
------------------------------------------------------------

- [co2_ou_device](https://github.com/arcticobservatory/co2_ou_device) repo
    --- Code and documentation for the observation unit itself

    - [Parts List](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-parts-list.md)
        --- parts used to build the observation units
    - [Circuit Schematic](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-schematic-v1.pdf)
        --- diagram of hardware and pin connections
    - [FiPy/Observation Unit Setup](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-fipy-setup.md)
        --- guide to installing the code on a FiPy and configuring the OU
    - [Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md)
        --- OU naming, data directory structure, and data file formats

- [co2_ou_server](https://github.com/arcticobservatory/co2_ou_server) repo
    --- Code and documentation for the companion server

    - [Database Scripts](https://github.com/arcticobservatory/co2_ou_server/tree/master/database)
        --- Shell scripts that import the text-based CO2 data into a
            SQLite database for analysis, plus Python scripts to generate plots

Code Layout in this Repository
--------------------------------------------------

The server is meant to be as simple as possible.
It uses the flask-restful framework inside of the UWSGI container.
The main source file is `src/server.py`.

The server accepts data uploads and "alive" pings from the CO2 OUs,
which are identified by hardware ID.
Uploaded data is kept in the `remote_data/` directory,
while records of "alive" pings are kept
in tab-separated-values files in the `var/pings/` directory
and also in a table in a SQLite data base `var/db.sqlite3`.

Scripts in the `database/` directory can import CO2 or other data into the
database and generate plots from it, as well as simple web pages to display
the plots. See the additional [database/README.md](database/) file for details.

**WARNING**: Accepting uploaded data from the internet
is often a risky activity,
and this server was not developed with security as a top concern.
There are probably exploits.
It is advised that you run this on a dedicated server/container
where damage from intrusion or malicious use can be contained.

- `src/` --- Source code

    - `server.py`
        --- Main server file
    - `server.ini.example`
        --- Example uwsgi configuration file,
            to be edited and copied to `server.ini`
    - `seqfile.py`
        --- Utility library for reading and writing sequential log files
            e.g. readings-0000.tsv, readings-0001.tsv, etc.

- `scripts/` --- Utility scripts

- `remote_data/`
    --- Directory for data uploaded by the CO2 OUs.
        Will be created by the server.
        See the [Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md)
        document in the device code repository
        for details of how the observation data is organized.

- `var/`
    --- Directory for server data.
        Will be created by the server.

    - `pings/` --- Directory of OU ping records in tab-separated-values format
    - `pub/` --- Directory of files to serve, such as generated data plots
    - `db.sqlite3` --- Database of pings (and optionally other data)

- `database/`
    --- Directory with scripts to build a database of uploaded CO2 data
        and generate plots from it. The scripts are controlled via a
        Makefile in the directory.
        There is an addition [database/README.md](database/) file with more details.

Running the server
--------------------------------------------------

### Installation

The code can be installed anywhere and run from its own directory.
However, it does need access to the Python Flask library.

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
