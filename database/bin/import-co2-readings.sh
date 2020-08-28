#!/bin/bash

set -e

DB_NAME=${1:-db.sqlite3}; shift || true
DATA_FILES="${@:-co2unit-*/data/readings/readings-*.tsv}"

add_trailing_newlines() {
    # Awk with a true condition and no action.
    # Prints all lines.
    # Adds a trailing newline if necessary.
    #
    # The avoids problems where incomplete records get concatenated and corrupted
    #
    awk 1 "$@"
}

FILTER_PATTERNS=(
    '/[^[:graph:][:space:]]/'   # Lines with non-printing characters (corrupt files)
    '/^co2unit-/!'  # Old format before the unit id was first, only test data
    '/1970-/'       # Readings with no RTC time, only a few readings from lab
)

for pat in ${FILTER_PATTERNS[@]}; do
    count=$(cat $DATA_FILES | sed -n "${pat}p" | wc -l)
    printf "## co2 filter pattern will drop %5d lines. To see run: sed -n '${pat}p'\n" $count >&2
done

co2_import_filter() {
    sed_script=''
    for pat in ${FILTER_PATTERNS[@]}; do
        sed_script+="${pat}d; "
    done
    echo "## Filtering: sed \"$sed_script\"" >&2
    sed "$sed_script"
}

# Create tables
sqlite3 $DB_NAME <<-ENDSQL
drop table if exists co2_readings;

CREATE TABLE co2_readings (
    unit_id     TEXT,
    nickname    TEXT,
    date        TEXT,
    time        TEXT,
    temp        NUMERIC,
    flash_count INTEGER,
    co2_01      INTEGER,
    co2_02      INTEGER,
    co2_03      INTEGER,
    co2_04      INTEGER,
    co2_05      INTEGER,
    co2_06      INTEGER,
    co2_07      INTEGER,
    co2_08      INTEGER,
    co2_09      INTEGER,
    co2_10      INTEGER
);
ENDSQL

# Pour data into database
add_trailing_newlines $DATA_FILES \
    | co2_import_filter \
    | sqlite3 $DB_NAME -csv -separator "	" \
        ".import /dev/stdin co2_readings" \
        2>&1 | ( grep -v 'filling the rest with NULL' || true ) \
        2>&1 | ( grep -v 'extras ignored' || true )

# Change "None" values to NULL in specific columns
for column in temp flash_count co2_{01..10}; do
    sqlite3 $DB_NAME "update co2_readings set $column=NULL where $column='None';"
    # Also set incomplete columns to NULL
    sqlite3 $DB_NAME "update co2_readings set $column=NULL where $column like 'N%';"
    sqlite3 $DB_NAME "update co2_readings set $column=NULL where $column='';"
done

# Postprocess imported data
sqlite3 $DB_NAME <<-ENDSQL

create index co2_index_by_unit_id
on co2_readings (unit_id, date, time);

ENDSQL
