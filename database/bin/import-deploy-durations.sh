#!/bin/bash

set -e

DB_FILE="${1:-db.sqlite3}"; shift || true

sqlite3 $DB_FILE <<-ENDSQL
drop table if exists deploy_durations;
ENDSQL

cat \
    |   sqlite3 $DB_FILE -csv -separator "	" \
        ".import /dev/stdin deploy_durations" \
        2>&1 | ( grep -v 'filling the rest with NULL' || true )

sqlite3 $DB_FILE <<-ENDSQL
update deploy_durations set bring_back_date=NULL where bring_back_date='';
ENDSQL
