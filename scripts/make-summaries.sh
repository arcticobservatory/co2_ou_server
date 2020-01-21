#!/bin/bash

echo 2>&1 "Refreshing web summaries at $(date -Iseconds)"

# Find script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Run Make
make -C "$DIR/../database/" DATA_DIR=../remote_data/ DB_DIR=../var WEB_PUB_DIR=../var/pub/ web
