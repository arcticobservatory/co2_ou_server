#!/bin/bash

START_DATE="${1:-2019-09-27}"
END_DATE="${2:-$(date +%Y-%m-%d)}"

cat var/pings/pings-*.tsv \
	| awk -v FS=$'\t' -v OFS=$'\t' \
		-v start="$START_DATE" -v end="${END_DATE}T99" \
		'start <= $1 && $1 <= end { print }' \
