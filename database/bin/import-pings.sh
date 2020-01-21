#!/bin/bash

set -e

DB_NAME=${1:-var/db.sqlite3}; shift || true
PING_FILES="${@:-var/pings/pings-*.tsv}"

pings_import_filter() {
    # Convert 'T' timestamps to separate date-time columns
    # 2019-10-07T03:23:39.980794 -> 2019-10-07      03:23:39.980794
    sed -E 's/^([0-9-]+)T([0-9:]+)/\1T\2\t\1\t\2/'
}

# Create tables
sqlite3 $DB_NAME <<-ENDSQL
drop table if exists pings;

CREATE TABLE pings (
    ping_ts     TEXT,
    ping_date   TEXT,
    ping_time   TEXT,
    unit_id     TEXT,
    nickname    TEXT,
    rssi_raw    INTEGER,
    rssi_dbm    INTEGER
);
ENDSQL

# Pour ping data into database
cat $PING_FILES \
    | pings_import_filter \
    | sqlite3 $DB_NAME -csv -separator "	" \
        ".import /dev/stdin pings" \
        2>&1 | ( grep -v 'filling the rest with NULL' || true )

# Postprocess imported data
sqlite3 $DB_NAME <<-ENDSQL

update pings set rssi_raw = NULL where rssi_raw = 'None';
update pings set rssi_dbm = NULL where rssi_dbm = 'None';

create index pings_index_by_unit_id
on pings (unit_id, ping_date, ping_time);

ENDSQL
