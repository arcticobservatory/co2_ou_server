#!/bin/bash

# To be run from the repo root
#
# - Activates the venv
# - Changes to the srouce directory
# - Runs the server

source .venv/bin/activate
cd src/
uwsgi --ini server.ini
