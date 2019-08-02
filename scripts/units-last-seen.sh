#!/bin/bash

pingsfile=$(find var/pings/* | sort | tail -n2)
# For each unique hardware id in the pings file
for hwid in $(cut -f2 $pingsfile | sort | uniq); do
	# Search backwards through the pings file for the last ping,
	# then re-order the output fields (site code, time, hardware id)
	tac $pingsfile | grep $hwid | head -n1 \
		| awk 'BEGIN {OFS="\t"}; {print $3, $1, $2}' 
done | sort
