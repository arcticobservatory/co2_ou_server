#!/bin/bash

set -e

DB_NAME=${1:-var/db.sqlite3}; shift || true
PING_FILES="${@:-var/pings/pings-*.tsv}"

pings_import_filter() {
    # Convert 'T' timestamps to separate date-time columns
    # 2019-10-07T03:23:39.980794 -> 2019-10-07      03:23:39.980794
    sed -E 's/^([0-9-]+)T/\1\t/'
}

# Create tables
sqlite3 $DB_NAME <<-ENDSQL
drop table if exists pings;

CREATE TABLE pings (
    ping_date   TEXT,
    ping_time   TEXT,
    unit_id     TEXT,
    nickname    TEXT,
    rssi_raw    INTEGER,
    rssi_dbm    INTEGER
);

CREATE TABLE IF NOT EXISTS deploy (
    unit_id     TEXT,
    site        TEXT,
    deploy_date TEXT,
    deploy_note TEXT
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

# Create a most-recent pings view
sqlite3 $DB_NAME <<-ENDSQL

drop view if exists pings_by_unit_id;
create view pings_by_unit_id
as
select
	u.unit_id,
	lp.nickname,
	d.site,
	-- d.action,
	-- d.deploy_date,
	lp.ping_date as last_ping,
	lp.rssi_dbm as last_dbm,
	dp.ping_date as last_deploy_ping,
	dp.rssi_dbm as last_deploy_dbm,
	case
		when d.deploy_date is not null
			then (select count(distinct ping_date) from pings where pings.unit_id = d.unit_id and ping_date > d.deploy_date)
		else null
	end	as deploy_ping_days,
	cast (( julianday() - julianday(d.deploy_date) ) as integer) as deploy_days,
	(select max(rssi_dbm)             from pings where pings.unit_id = d.unit_id and ping_date > d.deploy_date) as deploy_dbm_max,
	(select avg(rssi_dbm)             from pings where pings.unit_id = d.unit_id and ping_date > d.deploy_date) as deploy_dbm_mean,
	(select min(rssi_dbm)             from pings where pings.unit_id = d.unit_id and ping_date > d.deploy_date) as deploy_dbm_min
from (select distinct unit_id from pings) as u
left join pings as lp
	on lp.unit_id = u.unit_id
	and lp.ping_date = (select ping_date from pings where pings.unit_id = u.unit_id order by ping_date desc, ping_time desc limit 1)
	and lp.ping_time = (select ping_time from pings where pings.unit_id = u.unit_id order by ping_date desc, ping_time desc limit 1)
left join deploy as d
	on d.unit_id = u.unit_id
left join pings as dp
	on dp.unit_id = u.unit_id
	and dp.ping_date = (select ping_date from pings where pings.unit_id = u.unit_id and ping_date > d.deploy_date order by ping_date desc, ping_time desc limit 1)
	and dp.ping_time = (select ping_time from pings where pings.unit_id = u.unit_id and ping_date > d.deploy_date order by ping_date desc, ping_time desc limit 1)
	and d.site is not null
order by
	case
		-- group by deployment site
		when d.site is not null then 1
		else 2
	end,
	last_deploy_ping desc,
	deploy_ping_days desc,
	d.site desc,
	last_ping desc,
	lp.nickname
ENDSQL
