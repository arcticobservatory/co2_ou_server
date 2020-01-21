#!/bin/bash

fold_early_two_liners() {
    sed -E ':a; /^----- \([0-9, ]+\)$/ {N; s/\n/ EXC  /; ba}'
}

only_headlines() {
    grep '^-----'
}

reformat_dates() {
    #    (2019, 7, 28, 10, 0, 10, 6, 209)
    # to 2019-07-28 10:00:10
    cat \
        | sed -E 's/(\([0-9]+, )([0-9])(, [0-9]+, [0-9]+, [0-9]+, [0-9]+, [0-9]+, [0-9]+\))/\10\2\3/' \
        | sed -E 's/(\([0-9]+, [0-9]+, )([0-9])(, [0-9]+, [0-9]+, [0-9]+, [0-9]+, [0-9]+\))/\10\2\3/' \
        | sed -E 's/(\([0-9]+, [0-9]+, [0-9]+, )([0-9])(, [0-9]+, [0-9]+, [0-9]+, [0-9]+\))/\10\2\3/' \
        | sed -E 's/(\([0-9]+, [0-9]+, [0-9]+, [0-9]+, )([0-9])(, [0-9]+, [0-9]+, [0-9]+\))/\10\2\3/' \
        | sed -E 's/(\([0-9]+, [0-9]+, [0-9]+, [0-9]+, [0-9]+, )([0-9])(, [0-9]+, [0-9]+\))/\10\2\3/' \
        | sed -E 's/\(([0-9]+), ([0-9]+), ([0-9]+), ([0-9]+), ([0-9]+), ([0-9]+), [0-9]+, [0-9]+\)/\1-\2-\3 \4:\5:\6/' \
        | cat
}

date_range() {
    start_date=$1
    end_date=$2
    awk -v start_date="$start_date" -v end_date="$end_date" '
        BEGIN { in_range=0 }
        $2 >= start_date { in_range=1 }
        $2 > end_date { in_range=0 }
        in_range == 1 { print $0 }
'
}

restructure() {
    # Converts to tab-separated fields:
    # 1     2       3       4
    # date  time    level   message
    sed -E 's/----- ([0-9-]+) ([0-9:]+) ([A-Z]+) */\1\t\2\t\3\t/'
}

infer_dates() {
    # Assumes tab-separated from restructure
    # Inserts inferred date and time fields as fields 1 and 2
    # Inserts known error type as field 3
    # Result:
    # 1     2       3       4       5       6       7
    # idate itime   etype   odate   otime   level   message
    awk '
        BEGIN { FS="\t"; OFS="\t"}
        BEGIN { ldate=""; ltime=""}
        { odate = $1; otime = $2; msg=$4; etype="" }

        msg~/Uncaught exception/ { etype="uncaught" }
        msg~/[Ww]atch ?dog/ { etype="watchdog" }
        msg~/Signal quality/ { etype="signal" }
        msg~/backoff/ { etype="backoff" }
        msg~/transmitting/ { etype="transmit" }

        odate != "1970-01-01" { idate=odate; itime=otime; ldate=odate; ltime=otime; }
        odate == "1970-01-01" { idate=ldate; itime=ltime; }
        { print idate, itime, etype, $0 }
'
}

normalize_stream() {
    cat $@ \
        | fold_early_two_liners \
        | only_headlines \
        | reformat_dates \
        | restructure \
        | infer_dates \
        | cat
}

prepend_unit_id() {
    unit_id="$(echo $1 | sed -E 's/^.*(co2unit-[0-9a-f]+).*$/\1/')"
    sed "s/^/$unit_id\\t/"
}

normalize_and_unitid_each_file() {
    for logfile in "$@"; do
        normalize_stream "$logfile" \
            | prepend_unit_id "$logfile" \
            | cat
    done
}

import_to_db() {
    DB_NAME=$1; shift

# Create tables
sqlite3 $DB_NAME <<-ENDSQL
drop table if exists error_logs;

CREATE TABLE error_logs (
    unit_id TEXT,
    idate   TEXT,
    itime   TEXT,
    etype   TEXT,
    odate   TEXT,
    otime   TEXT,
    level   TEXT,
    message TEXT
);
ENDSQL

    # Pour data into db
    normalize_and_unitid_each_file "$@" \
        | sqlite3 $DB_NAME -csv -separator "	" \
            ".import /dev/stdin error_logs" \
            2>&1 | ( grep -v 'filling the rest with NULL' || true )
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    import_to_db "$@"
fi
