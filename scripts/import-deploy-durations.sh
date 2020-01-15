#!/bin/bash

set -e

DB_NAME=${1:-var/db.sqlite3}; shift || true

sqlite3 $DB_NAME <<-ENDSQL
drop table if exists deploy_durations;
ENDSQL

cat \
    |   sqlite3 $DB_NAME -csv -separator "	" \
        ".import /dev/stdin deploy_durations" \
        2>&1 | ( grep -v 'filling the rest with NULL' || true )

sqlite3 $DB_NAME <<-ENDSQL
update deploy_durations set bring_back_date=NULL where bring_back_date='';
ENDSQL
