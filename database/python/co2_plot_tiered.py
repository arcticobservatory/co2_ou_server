import sqlite3
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import math

import warnings

# Use a colorblind-friendly palette
plt.style.use('tableau-colorblind10')

# Explicitly register Pandas date converters for MatPlotLib
# Pandas warns us if we don't
pd.plotting.register_matplotlib_converters()

co2_cols = ["co2_{:02d}".format(i) for i in range(1,11)]

# Styles

site_label_style = {
        "bbox": {
            "facecolor": 'ghostwhite',
            "alpha": 0.8,
            "edgecolor": 'white',
            #"edgecolor": 'lightgrey',
        }
}

co2_line_style = {
        "linewidth": 0.5,
        "color": "black",
}
co2_line_styles_status = {
        "en_route": { "linestyle": "dashed" },
        "lab_check": { "linestyle": "dotted" },
}

co2_fill_style = {
        "alpha": 0.7,
        "color": "lightgrey",
}
co2_fill_styles_status = {
        "en_route": { "alpha": "0.5" },
        "lab_check": { "alpha": "0.3" },
}

temp_line_style = {
        "linewidth": 0.5,
}

grid_style = {
        "linewidth": 0.5,
        "color": "0.9",
}

def arg_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Plot CO2 data")
    parser.add_argument('dbfile', type=str)
    parser.add_argument('plotfile', type=str)
    parser.add_argument('--xmin', type=str, required=False, default=None,
            help="Minumum date to plot (ISO fmt, e.g. 2019-08-01')")
    parser.add_argument('--xmax', type=str, required=False, default=None,
            help="Maximum date to plot (ISO fmt, e.g. 2020-08-01')")
    parser.add_argument('--co2-max', type=int, required=False, default=None,
            help="Set max co2 y-limit to this value (ppm)")
    parser.add_argument('--min-tier', type=int, required=False, default=None,
            help="Include only deployments with a 'tier' value >= this value")
    parser.add_argument('--max-tier', type=int, required=False, default=None,
            help="Include only deployments with a 'tier' value <= this value")
    parser.add_argument('--recent-days', type=int, default=None)
    #parser.add_argument('--dpi', type=int, default="96")
    #parser.add_argument('--same-ranges', action='store_true')
    #parser.add_argument('--co2-max', type=int, default=None)
    return parser

def select_deploys(db, xmin, xmax, min_tier, max_tier):

    sql = """
        -- start with all deployments
        select
            d.tier, d.site, d.unit_id, d.nickname, d.status,
            d.start_ts, d.end_ts,
            min(c.date) as min_co2_date, max(c.date) as max_co2_date
        from deploy_durations_tiered d
        left join co2_readings c
            on c.unit_id = d.unit_id
            and (d.start_ts is null or d.start_ts <= c.date)
            and (d.end_ts is null or c.date <= d.end_ts)
        where {where_conds}
        group by
            tier, site, d.unit_id, d.nickname, d.status, d.start_ts, d.end_ts

        -- add in measurements that never had a deployment
        UNION ALL
        select
            null as tier, null as site,
            c.unit_id,
            c.nickname, null as status,
            null as start_ts, null as end_ts,
            min(c.date) as min_co2_date, max(c.date) as max_co2_date
        from co2_readings c
        where {where_conds}
            and not exists (
                    select unit_id
                    from deploy_durations_tiered where unit_id = c.unit_id
                )

        group by
            c.unit_id, c.nickname

        order by
            tier desc, site, start_ts, d.nickname, c.nickname, c.unit_id, start_ts;
    """

    where_conds = ["1"]
    params = []

    if xmin is not None:
        where_conds.append("c.date >= ?")
        params.append(xmin)

    if xmax is not None:
        where_conds.append("c.date <= ?")
        params.append(xmax)

    if min_tier is not None:
        where_conds.append("tier is not null and tier >= ?")
        params.append(min_tier)

    if max_tier is not None:
        where_conds.append("tier is not null and tier <= ?")
        params.append(max_tier)

    sql = sql.format(where_conds = "\nand ".join(where_conds))
    params = params * 2     # because the where conditions are used twice

    deploys = pd.read_sql(sql, db, params=params,
            coerce_float=False,
            parse_dates=['start_ts','end_ts','min_co2_date', 'max_co2_date'])

    #print(sql); print(params); print(deploys)

    deploys['tier'] = deploys['tier'].astype("Int64")

    # Drop rows where the timestamp value could not be parsed
    deploys = deploys[~deploys.min_co2_date.isnull()]
    deploys = deploys[~deploys.max_co2_date.isnull()]

    return deploys

def determine_xlim(xmin, xmax, min_tier, max_tier, deploys):
    deploy_min = deploys.start_ts.dropna().min()
    deploy_max = deploys.end_ts.dropna().max()
    min_co2_date = deploys.min_co2_date.dropna().min()

    today = pd.Timestamp.now().normalize()
    one_day = pd.Timedelta(days=1)

    if xmin:
        xmin = pd.Timestamp(xmin)
    elif (min_tier or max_tier) and deploys.start_ts.notnull().all():
        xmin = deploy_min - one_day
    elif not pd.isnull(min_co2_date):
        xmin = min_co2_date - one_day
    else:
        xmin = today - one_day

    if xmax:
        xmax = pd.Timestamp(xmax)
    elif (min_tier or max_tier) and deploys.end_ts.notnull().all():
        xmax = deploy_max + one_day
    else:
        xmax = today + one_day

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

def set_date_ticks(ax, xmin, xmax):

    major_locator = mpl.dates.AutoDateLocator()
    if xmax - xmin <= pd.Timedelta(days=31):
        minor_locator = mpl.dates.HourLocator(byhour=[0,8,16])
    else:
        minor_locator = mpl.dates.DayLocator(bymonthday=[1,8,15,22,29])
    major_formatter = mpl.dates.ConciseDateFormatter(major_locator)

    ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_minor_locator(minor_locator)
    ax.xaxis.set_major_formatter(major_formatter)

    #ax.set_xlabel("Date")

def select_co2_for_deploy(deploy_row):
    sql = """
        select date || 'T' || time as co2_ts, *
        from co2_readings c
        where {where_conds}
        order by date, time
    """

    where_conds = ["unit_id = ?"]
    params = [deploy_row.unit_id]

    if not pd.isnull(deploy_row.start_ts):
        where_conds.append("date >= ?")
        params.append(deploy_row.start_ts.isoformat())

    if not pd.isnull(deploy_row.end_ts):
        where_conds.append("date <= ?")
        params.append(deploy_row.end_ts.isoformat())

    sql = sql.format(where_conds = " and ".join(where_conds))
    co2 = pd.read_sql(sql, db, params=params,
            coerce_float=False, parse_dates=['co2_ts', 'date', 'time'])

    return co2

def massage_co2_data(co2):

    # The CO2 data has problems with corrupted rows

    # Drop rows where the timestamp value could not be parsed
    co2 = co2[~co2.co2_ts.isnull()]

    # Use timestamp as the index
    co2.set_index('co2_ts', drop=False, inplace=True)

    # Run through each numeric column and sets non-numeric values to NaN
    # (errors='coerce' -> coerce to NaN)
    for col in "temp flash_count co2_01 co2_02 co2_03 co2_04 co2_05 co2_06 co2_07 co2_08 co2_09 co2_10".split():
        co2[col] = pd.to_numeric(co2[col], errors='coerce')

    # Add mean and std-dev columns
    co2["co2_mean"] = co2[co2_cols].mean(axis=1)
    co2["co2_std"] = co2[co2_cols].std(axis=1)

    return co2

def calculate_bin_width(ax):

    # Attempt to bin values into roughly this width on the page (pts)
    bin_size_pts = 1

    # Extract figure size data
    bbox_ins = ax.get_window_extent().transformed(
            ax.get_figure().dpi_scale_trans.inverted())
    width_pts = bbox_ins.width * 72

    # When retrieving datetime axis limits from Matplotlib,
    # they come out as Julian ordinal days.
    xmin, xmax = ax.get_xlim()
    xmin = pd.Timestamp.fromordinal(int(xmin))
    xmax = pd.Timestamp.fromordinal(int(xmax))
    width_x = xmax - xmin

    bin_width = width_x * bin_size_pts / width_pts

    if bin_width > pd.Timedelta(days=1):
        normalized = bin_width.floor("D")
    elif bin_width > pd.Timedelta(hours=1):
        normalized = bin_width.floor("H")
    else:
        normalized = None

    # print("Data bin size: Target on-page width {} pts = {}. Normalizing to {}.".format(bin_size_pts, bin_width, normalized))
    return normalized

def resample_data(co2, bin_width):
    co2_series = co2['co2_mean']
    temp_series = co2['temp']

    # Strip out outliner max temp values
    # Note: This produces a ton of FutureWarnings
    # See https://stackoverflow.com/a/46721064
    warnings.simplefilter(action='ignore', category=FutureWarning)
    temp_maxout_value = 85.0
    temp_series = temp_series.loc[temp_series != temp_maxout_value]

    if bin_width != None:
        co2_series = co2_series.resample(bin_width, origin='start_day').mean()
        temp_series = temp_series.resample(bin_width, origin='start_day').mean()

    return co2_series, temp_series

def draw_co2(line_ax, fill_ax, co2_series, status):
    # Draw co2 line and fill
    line_style = co2_line_style
    fill_style = co2_fill_style

    if status in co2_line_styles_status:
        line_style = {**line_style, **co2_line_styles_status[status]}

    if status in co2_fill_styles_status:
        fill_style = {**fill_style, **co2_fill_styles_status[status]}

    line_ax.plot(co2_series.index, co2_series, **line_style)
    fill_ax.fill_between(co2_series.index, 0, co2_series, **fill_style)

def draw_temp(ax, temp_series):

    # This plot requires making segments between pairs of temps.
    # If there is only one reading it will not work.
    if len(temp_series) < 2:
        return

    # Use multi-colored line technique from:
    # https://matplotlib.org/3.1.1/gallery/lines_bars_and_markers/multicolored_line.html
    #
    # Instead of a line, turn the list of points into a collection of
    # segments from each point to the next. Then give each segment a
    # separate color.

    # Colormap for temperature
    cmap = mpl.colors.LinearSegmentedColormap.from_list("coolblackwarm",
            ['blue','grey','red'])
    norm = mpl.colors.Normalize(-5, 5, clip=True)

    # First convert dates to numbers
    numericdates = mpl.dates.date2num(temp_series.index)

    # Create a list of points
    # [[date0, temp0], [date1,temp1], ...]
    point_list = np.array([numericdates, temp_series]).T

    # Reshape to list of 1-element list of points (-1 means infer size)
    # [ [[date0,temp0]], [[date1,temp1]], ...]
    point_list = point_list.reshape(-1, 1, 2)

    # Copy, shift, and concatenate on the second axis to get a list of two-point line segments
    # [ [[date0,temp0],[date1,temp1]], [[date1,temp1],[date2,temp2]], ...]
    segments = np.concatenate([point_list[:-1], point_list[1:]], axis=1)

    # Create a LineCollection from segments (each segment is one line in the collection)
    lc = mpl.collections.LineCollection(segments, cmap=cmap, norm=norm, **temp_line_style)

    # Calculate the average y value between each point and use it as the color map input
    segment_avg_temps = (temp_series[:-1] + temp_series[1:]) / 2
    lc.set_array(segment_avg_temps)

    line = ax.add_collection(lc, autolim=True)
    return line

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

def draw_site_label(ax, site_label):
    t = ax.annotate(site_label,
            xy=(0,1), xycoords="axes fraction",
            xytext=(5,-5), textcoords="offset points",
            horizontalalignment='left', verticalalignment='top',
            **site_label_style)
    return t

def build_plot(db, xmin=None, xmax=None, recent_days=None, min_tier=None, max_tier=None, co2_max=None):

    if recent_days and not xmin:
        xmin = pd.Timestamp.now().normalize() - pd.Timedelta(days=recent_days)
        xmin = xmin.isoformat()

    deploys = select_deploys(db, xmin, xmax, min_tier, max_tier)
    grouped = group_deploys(deploys)
    num_groups = len(grouped)

    # Initialize figure
    print("num_groups:", num_groups)
    fig, axes = plt.subplots(nrows=num_groups, ncols=1, sharex=True)
    print("axes:", repr(axes))
    # un-squeeze the axes object if only one subplot, convert back to list
    if num_groups==1:
        axes = [axes]

    # Begin x axis setup
    # It is important to set timestamp axes early, so that Matplotlib knows
    # that the axis uses dates
    xmin, xmax = determine_xlim(xmin, xmax, min_tier, max_tier, deploys)
    axes[0].set_xlim(xmin, xmax)

    # Set figure size
    subplot_height_ins = 1
    text_line_height_pts = plt.rcParams.get("font.size") * 1.5
    margin_ins = (2 * text_line_height_pts / 72.0)
    height_ins = subplot_height_ins * num_groups + margin_ins
    fig.set_size_inches(7.5, height_ins)

    bin_width = calculate_bin_width(axes[-1])

    # Main loop: each deployment group -> subplot
    for i, (group_name, group) in enumerate(grouped):
        # Current subplot axes
        co2_ax = axes[i]

        # Subplot setup

        # CO2 axis setup
        co2_ax.autoscale(True, "y")
        co2_ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
        co2_ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(
            lambda x, pos: "{:,.0f}".format(x).replace(",", " ")))
        co2_ax.set_ylabel("CO2 (ppm)")
        if co2_max:
            co2_ax.set_ylim(0, co2_max)

        # Create a separate axis to draw the CO2 fill on
        co2_fill_ax = co2_ax
        co2_fill_ax = co2_ax.twinx()
        co2_fill_ax.set_yticks([])

        # Temperature axis setup
        temp_ax = co2_ax.twinx()
        temp_ax.autoscale(True, "y")
        temp_ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
        #temp_ax.set_ylim(-25, 25)
        temp_ax.set_ylabel("Temp (C)")

        # Draw labels and grid on z-order specific axes
        draw_site_label(temp_ax, format_site_name(group))
        co2_ax.grid(True, **grid_style)

        for j, deploy_row in group.iterrows():

            co2 = select_co2_for_deploy(deploy_row)
            co2 = massage_co2_data(co2)
            co2_series, temp_series = resample_data(co2, bin_width)
            draw_co2(co2_ax, co2_fill_ax, co2_series, deploy_row.status)
            draw_temp(temp_ax, temp_series)

        co2_ax.autoscale_view(scalex=False, scaley=True)
        co2_fill_ax.set_ylim(co2_ax.get_ylim())
        temp_ax.autoscale_view(scalex=False, scaley=True)

    # Finishing touches
    set_date_ticks(axes[-1], xmin, xmax)
    fig.tight_layout()

    return fig

if __name__ == "__main__":
    parser = arg_parser()
    args = parser.parse_args()

    db = sqlite3.connect(args.dbfile)
    plotfile = args.plotfile

    args = vars(args)
    del(args["dbfile"])
    del(args["plotfile"])

    fig = build_plot(db, **args)

    fig.savefig(plotfile)
