#!/bin/bash

set -e

DB_FILE="$1"
TSV="$2"

sqlite3 $DB_FILE <<-ENDSQL
drop table if exists deploy_durations_tiered;

CREATE TABLE deploy_durations_tiered (
    unit_id     TEXT,
    nickname    TEXT,
    site        TEXT,
    tier        INTEGER,
    status      TEXT,
    start_ts    TEXT,
    end_ts      TEXT,
    note        TEXT
);
ENDSQL

filter_blank_lines_and_comments() {
    sed 's/#.*$//;/^[[:space:]]*$/d'
}

filter_expected_warning_text() {
    ( grep -v 'filling the rest with NULL' || true )
}

if [[ -f "$TSV" ]]; then
    cat "$TSV" \
        | tail -n +2 \
        | filter_blank_lines_and_comments \
        | sqlite3 $DB_FILE -csv -separator "	" \
            ".import /dev/stdin deploy_durations_tiered" \
            2>&1 \
        | filter_expected_warning_text
else
    echo 2>&1 "Table file not found. Using empty table."
    echo 2>&1 "To specify deploy data, create table file: $TSV"
fi

for column in nickname site tier status start_ts end_ts note; do
    sqlite3 $DB_FILE "update deploy_durations_tiered set $column=NULL where $column='';"
done
