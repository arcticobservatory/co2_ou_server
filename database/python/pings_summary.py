import sqlite3
import jinja2
import pandas as pd
import numpy as np

def fetch_pings_by_unit_id(db):
    """ Elaborate pings-by-unit-id query

        Takes a database connection, returns a pandas Dataframe with results.
    """

    sql = """
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
        left join deploy_durations as d
                on d.unit_id = u.unit_id
                and d.bring_back_date is null
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
        """

    cur = db.execute(sql)
    rows = cur.fetchall()

    col_names = [column[0] for column in cur.description]
    df = pd.DataFrame.from_records(data=rows, columns=col_names)
    db.close()

    # Massage data
    intfmt = lambda n: str(int(n)) if n==n else ''
    df.deploy_days = df.deploy_days.apply(intfmt)
    df.deploy_ping_days = df.deploy_ping_days.apply(intfmt)
    df = df.replace(np.nan, '')

    return df

if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Generate pings summary")
    parser.add_argument('dbfile', type=str)
    parser.add_argument('templatefile', type=str)

    args = parser.parse_args()

    db = sqlite3.connect(args.dbfile)
    pings_by_unit_id = fetch_pings_by_unit_id(db)

    table_html = pings_by_unit_id.to_html(
                border = 0,
                justify = "right",
                na_rep = "",
                float_format = lambda n: "{:.1f}".format(n) if n==n else "",
                )

    with open(args.templatefile) as f:
        template = jinja2.Template(f.read())

    print(template.render(table=table_html))
