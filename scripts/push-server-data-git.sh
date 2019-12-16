#!/bin/bash

echo 2>&1 "Running autocommit at $(date -Iseconds)"

# Find script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Add current ping data to repository data
(
	# script assumes it's being run from the parent directory
	cd "$DIR/.."
	./scripts/push-server-data.sh
)

# Push data via git
(
	set -ex
	cd "$DIR/../remote_data"
	git checkout incoming-data-$HOSTNAME
	git add .
	git commit -m "Autocommit data $(date +"%Y-%m-%d %a")"
	git push
)
