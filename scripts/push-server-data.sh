#!/bin/bash

servername="$HOSTNAME"
pings_src="var/pings"
pings_dest="remote_data/server-$HOSTNAME/$pings_src"

mkdir -p "$pings_dest"
rsync -rt "$pings_src/" "$pings_dest/"
