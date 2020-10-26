import sqlite3
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

# Use a colorblind-friendly palette
plt.style.use('tableau-colorblind10')

# Explicitly register Pandas date converters for MatPlotLib
# Pandas warns us if we don't
pd.plotting.register_matplotlib_converters()

# Styles

grid_style = {
        "linewidth": 0.5,
        "color": "0.9",
}
deploy_line_style = {
        "linewidths": 1,
}
deploy_line_styles_status = {
        "en_route": { "linestyles": "dashed", "color": "0.3" },
        "lab_check": { "linestyles": "dotted", "color": "0.5" },
}

def argparser():
    import argparse
    parser = argparse.ArgumentParser(description="Plot pings data")
    parser.add_argument('dbfile', type=str)
    parser.add_argument('plotfile', type=str)
    parser.add_argument('--xmin', type=str, required=False, default=None,
            help="Minumum date to plot (ISO fmt, e.g. 2019-08-01')")
    parser.add_argument('--xmax', type=str, required=False, default=None,
            help="Maximum date to plot (ISO fmt, e.g. 2020-08-01')")
    parser.add_argument('--min-tier', type=int, required=False, default=None,
            help="Include only deployments with a 'tier' value >= this value")
    return parser

def select_deploys(db, xmin, xmax, min_tier):

    sql = """
        -- start with all deployments
        select
            d.tier, d.site, d.unit_id, d.nickname, d.status,
            d.start_ts, d.end_ts,
            min(p.ping_ts) as min_ping_ts, max(p.ping_ts) as max_ping_ts
        from deploy_durations_tiered d
        left join pings p
            on d.unit_id = p.unit_id
            and (d.start_ts is null or d.start_ts <= p.ping_ts)
            and (d.end_ts is null or p.ping_ts <= d.end_ts)
        where {where_conds}
        group by
            tier, site, d.unit_id, d.nickname, d.status, d.start_ts, d.end_ts

        -- add in pings that never had a deployment
        UNION ALL
        select
            null as tier, null as site,
            p.unit_id,
            p.nickname, null as status,
            null as start_ts, null as end_ts,
            min(p.ping_ts) as min_ping_ts, max(p.ping_ts) as max_ping_ts
        from pings p
        where {where_conds}
            and not exists (
                    select unit_id
                    from deploy_durations_tiered where unit_id = p.unit_id
                )

        group by
            p.unit_id, p.nickname

        order by
            tier desc, site, start_ts, d.nickname, p.nickname, p.unit_id, start_ts;
    """
    where_conds = ["1"]
    params = []

    if xmin is not None:
        where_conds.append("p.ping_ts >= ?")
        params.append(xmin)

    if xmax is not None:
        where_conds.append("p.ping_ts <= ?")
        params.append(xmax)

    if min_tier is not None:
        where_conds.append("tier is not null and tier >= ?")
        params.append(min_tier)

    sql = sql.format(where_conds = "\nand ".join(where_conds))
    params = params * 2     # because the where conditions are used twice

    deploys = pd.read_sql(sql, db, params=params,
            coerce_float=False,
            parse_dates=['start_ts','end_ts','min_ping_ts', 'max_ping_ts'])

    #print(sql); print(params); print(deploys)
    deploys['tier'] = deploys['tier'].astype("Int64")
    return deploys

def select_pings(db, deploy_row):
    sql = """
        select p.ping_ts, p.nickname
        from pings p
        where {where_conds}
        order by ping_ts
    """

    where_conds = ["p.unit_id = ?"]
    params = [deploy_row.unit_id]

    if not pd.isnull(deploy_row.start_ts):
        where_conds.append("p.ping_ts >= ?")
        params.append(deploy_row.start_ts.isoformat())

    if not pd.isnull(deploy_row.end_ts):
        where_conds.append("p.ping_ts <= ?")
        params.append(deploy_row.end_ts.isoformat())

    sql = sql.format(where_conds = " and ".join(where_conds))
    pings = pd.read_sql(sql, db, params=params,
            coerce_float=False, parse_dates=['ping_ts'])
    return pings

def determine_xlim(xmin, xmax, min_tier, deploys):
    deploy_min = deploys.start_ts.dropna().min()
    deploy_max = deploys.end_ts.dropna().max()
    ping_min = deploys.min_ping_ts.dropna().min()
    ping_max = deploys.max_ping_ts.dropna().max()

    today = pd.Timestamp.now().normalize()
    one_day = pd.Timedelta(days=1)

    if xmin:                                    xmin = pd.Timestamp(xmin)
    elif min_tier and deploys.start_ts.notnull().all():   xmin = deploy_min - one_day
    elif not pd.isnull(ping_min):               xmin = ping_min - one_day
    else:                                       xmin = today - one_day

    if xmax:                                    xmax = pd.Timestamp(xmax)
    elif min_tier and deploys.end_ts.notnull().all():     xmax = deploy_max + one_day
    else:                                       xmax = today + one_day

    return xmin, xmax

def deploys_overlap(ga, gb):

    for _, a in ga.iterrows():
        for _, b in gb.iterrows():

            ast = a.start_ts; aen = a.end_ts
            bst = b.start_ts; ben = b.end_ts

            if ast and aen and bst and ben:     clear = aen <= bst or ben <= ast
            elif ast and ben:                   clear = ben <= ast
            elif aen and bst:                   clear = aen <= bst
            else:                               clear = False

            if not clear: return True
    return False

def group_deploys(deploys):
    # First, group by site and unit
    grouped = deploys.groupby(by=["tier","site","unit_id"], sort=False, dropna=False)

    # Secong, combine (compress) different deployments at the same site,
    # so long as they don't overlap
    compressed = []
    compress = None
    for (tier, site, unit_id), group in grouped:
        if compress is None:
            compress = group
        elif site == compress.iloc[-1].site and not deploys_overlap(compress, group):
            compress = pd.concat([compress, group])
        else:
            ctuple = ((tier, site), compress)
            compressed.append(ctuple)
            compress = group
    # Add last compress group
    if compress is not None:
        compress = ((tier, site), compress)
        compressed.append(compress)

    return compressed

def format_site_name(group_df):
    sites = group_df.site.unique()
    unit_id = group_df.iloc[-1].unit_id

    if not len(sites)==1:
        raise ValueError("Expected group to have only 1 site: {}".format(group_df))
    site = sites[0]

    if site:
        return site
    else:
        #return "{} [not deployed]".format(unit_id)
        return "[not deployed]"

def format_nickname(group_df, last_pings_df):

    deploy_nick = group_df.iloc[-1].nickname
    if deploy_nick:
        return deploy_nick

    if len(last_pings_df):
        ping_nick = last_pings_df.iloc[-1].nickname
        if ping_nick:
            return ping_nick

    unit_id = group_df.iloc[-1].nickname
    return unit_id

def draw_pings(ax, yval, pings):
    # Pings are drawn by day.

    # We are also grouping consecutive days into one bar object,
    # to avoid excessive paths in a vector plot.
    streaks = []
    streak_start = None
    streak_end = None
    one_day = pd.Timedelta(days=1)

    for ping_ts in pings.ping_ts:

        ping_day = ping_ts.normalize()

        if streak_end and ping_day <= streak_end + one_day:
            # Continue streak
            streak_end = ping_day

        else:
            # Break streak
            if streak_end:
                streaks.append((streak_start, streak_end))

            # New streak
            streak_start = ping_day
            streak_end = ping_day

    # Add final streak
    if streak_end:
        streaks.append((streak_start, streak_end))

    # Convert start/end streaks to start/length bars
    bars = [(streak_start, streak_end-streak_start+one_day) \
            for (streak_start,streak_end) in streaks]

    ping_bar_height = .6
    ylow = yval - ping_bar_height / 2.0

    ax.broken_barh(bars, (ylow, ping_bar_height))

def draw_deploy_markers(ax, yval, deploy, xmin, xmax):

    deploy_barrier_height = .8
    ylow = yval - deploy_barrier_height / 2.0
    yhigh = yval + deploy_barrier_height / 2.0

    if deploy.status in deploy_line_styles_status:
        line_style = {**deploy_line_style,
                        **deploy_line_styles_status[deploy.status]}
    else:
        line_style = deploy_line_style

    if not pd.isnull(deploy.start_ts):
        xval = deploy.start_ts.normalize()
        ax.vlines(xval, ylow, yhigh, **line_style)
        xmin = xval

    if not pd.isnull(deploy.end_ts):
        xval = deploy.end_ts.normalize() #+ pd.Timedelta(days=1)
        ax.vlines(xval, ylow, yhigh, **line_style)
        xmax = xval

    if not pd.isnull(deploy.start_ts) or not pd.isnull(deploy.end_ts):
        ax.hlines(yval, xmin, xmax, **line_style)

def build_plot(db, xmin=None, xmax=None, min_tier=None):
    deploys = select_deploys(db, xmin, xmax, min_tier)
    grouped = group_deploys(deploys)
    num_groups = len(grouped)

    # Initialize figure
    fig, ax = plt.subplots()

    # Begin x axis setup
    # It is important to set timestamp axes early, so that Matplotlib knows
    # that the axis uses dates
    xmin, xmax = determine_xlim(xmin, xmax, min_tier, deploys)
    ax.set_xlim(xmin, xmax)

    # Begin y axis setup
    yvals = []
    ylabels_left = []
    ylabels_right = []

    # Main loop: each deployment group -> row of plot

    for i, (group_name, group) in enumerate(grouped):

        yval = num_groups - i
        yvals.append(yval)

        # Each deployment in row

        for j, deploy_row in group.iterrows():
            pings = select_pings(db, deploy_row)
            draw_pings(ax, yval, pings)
            if len(pings):
                last_nick = pings.iloc[-1].nickname
            draw_deploy_markers(ax, yval, deploy_row, xmin, xmax)

        ylabels_left.append(format_site_name(group))
        ylabels_right.append(format_nickname(group, pings))

    # Format x axis
    major_locator = mpl.dates.AutoDateLocator()
    minor_locator = mpl.dates.DayLocator(bymonthday=[1,8,15,22,29])
    ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_minor_locator(minor_locator)
    ax.xaxis.set_major_formatter(mpl.dates.ConciseDateFormatter(major_locator))

    # Format y axis (left)
    ax.set_ylim(.5, num_groups+.5)
    ax.set_yticks(yvals)
    ax.set_yticklabels(ylabels_left)

    # Create a right-hand y axis for secondary info
    ax2 = ax.twinx()
    ax2.set_ylim(*ax.get_ylim())
    ax2.set_yticks(yvals)
    ax2.set_yticklabels(ylabels_right)

    # Other decoration
    ax.grid(True, **grid_style)

    # Set figure size
    y_row_size_pts = plt.rcParams.get("font.size") * 1.5
    height_pts = (num_groups+3) * y_row_size_pts
    fig.set_size_inches(7.5, (height_pts//72)+1)
    fig.tight_layout()

    return fig

if __name__ == "__main__":
    parser = argparser()
    args = parser.parse_args()

    db = sqlite3.connect(args.dbfile)
    plotfile = args.plotfile

    args = vars(args)
    del(args["dbfile"])
    del(args["plotfile"])

    fig = build_plot(db, **args)

    fig.savefig(plotfile)
