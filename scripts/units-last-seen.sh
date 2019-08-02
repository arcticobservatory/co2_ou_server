#!/bin/bash

pingsfile=$(find var/pings/* | sort | tail -n2)
# For each unique hardware id in the pings file
for hwid in $(cut -f2 $pingsfile | sort | uniq); do
	# tac --- Search backwards through the pings file for the last ping,
	# awk --- Re-order the output fields (site code, time, hardware id)
	# sed --- Reformat the ISO date to be more readable
	tac $pingsfile | grep $hwid | head -n1 \
		| awk 'BEGIN {OFS="\t"}; {print $3, $1, $2}' \
		| sed -E 's/([0-9-]{10})T([0-9:]{8}).[0-9]+/\1 \2/'
done | sort
