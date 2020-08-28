import sqlite3
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import math

# Use a colorblind-friendly palette
plt.style.use('tableau-colorblind10')

# Explicitly register Pandas date converters for MatPlotLib
# Pandas warns us if we don't
pd.plotting.register_matplotlib_converters()

co2_cols = ["co2_{:02d}".format(i) for i in range(1,11)]

def fetch_co2_data(db):
    co2_readings_sql = """
    select
        d.site,
        c.date || 'T' || c.time as datetime,
        c.*
    from co2_readings c
    left join deploy_durations d
        on c.unit_id = d.unit_id
        and c.date >= d.deploy_date
        and (d.bring_back_date is null or c.date <= d.bring_back_date)
    order by
        date, time
    """
    co2_readings = pd.read_sql(co2_readings_sql, db, parse_dates=['datetime'])
    return co2_readings

def add_co2_std_column(co2_readings):
    co2_readings = co2_readings.copy()
    co2_readings["co2_mean"] = co2_readings[co2_cols].mean(axis=1)
    co2_readings["co2_std"] = co2_readings[co2_cols].std(axis=1)
    return co2_readings

def filter_bad_values(co2_readings):
    df = co2_readings
    print("Dropping rows with bad datetime values.\n{}" .format(df[df.datetime.isnull()]))
    df = df[~df.datetime.isnull()]

    for col in "temp flash_count co2_01 co2_02 co2_03 co2_04 co2_05 co2_06 co2_07 co2_08 co2_09 co2_10".split():
        df[col] = pd.to_numeric(df[col], errors='coerce')

    print("New info:\n{}".format(df.info()))
    return df

def fetch_deploy_data(db):
    deploys = pd.read_sql('select * from deploy_durations', db, parse_dates=['deploy_date','bring_back_date'])
    return deploys

def set_up_axes(co2s, sites=[], co2_col="co2_mean",
            same_range_co2=None, same_range_temp=None, dpi=96):

    fig, co2_axes = plt.subplots(nrows=len(sites), ncols=1, sharex=True)
    print('sites', sites, 'co2_axes', co2_axes)
    if not hasattr(co2_axes, '__iter__'):
        co2_axes = [co2_axes]
    # Create an axis for temperature
    temp_axes = [ax.twinx() for ax in co2_axes]

    fig.dpi = dpi

    fig_max_w_in = 8.0
    fig_max_h_in = 10.0
    fig_max_plots = 15
    fig_h_in = fig_max_h_in * (len(sites)/float(fig_max_plots))
    fig.set_size_inches(fig_max_w_in, fig_h_in)

    # All subplots will use the same X axis
    #
    # It's also importan to call this early to tell matplotlib we are using
    # dates. Otherwise we may get errors trying to draw with Timestamp objects.
    xmin = co2s.datetime.min()
    xmax = co2s.datetime.max()
    plt.xlim(xmin, xmax)

    major_locator = mpl.dates.AutoDateLocator()
    if xmax - xmin <= pd.Timedelta(days=31):
        minor_locator = mpl.dates.HourLocator(byhour=[0,8,16])
    else:
        minor_locator = mpl.dates.DayLocator(bymonthday=[1,8,15,22,29])
    major_formatter = mpl.dates.ConciseDateFormatter(major_locator)
    for ax in co2_axes:
        ax.xaxis.set_major_locator(major_locator)
        ax.xaxis.set_minor_locator(minor_locator)
        ax.xaxis.set_major_formatter(major_formatter)

    co2_axes[-1].set_xlabel("Date")

    # Set limits for each Y axis
    for i, site in enumerate(reversed(sites)):

        site_readings = co2s.loc[co2s.site == site]
        co2_ax = co2_axes[i]
        temp_ax = temp_axes[i]

        for ax, same_range, col in [
                (co2_ax, same_range_co2, co2_col),
                (temp_ax, same_range_temp, "temp")]:

            # Set y axis limits
            if isinstance(same_range, tuple):
                ymin, ymax = same_range
            else:
                if same_range == True: data = co2s[col]
                else: data = site_readings[col]
                ymin, ymax = (data.min(), data.max())

            margin = 0.05
            ymin -= margin * (ymax - ymin)
            ymax += margin * (ymax - ymin)
            ax.set_ylim([ymin, ymax])

            # Set y axis formatting
            ax.yaxis.set_major_locator(mpl.ticker.AutoLocator())
            ax.yaxis.set_minor_locator(mpl.ticker.AutoMinorLocator())
            ax.tick_params(axis = 'both', which = 'major', labelsize = 'x-small')

    fig.text(0, 0.8, "CO2 (ppm)", ha='left', va='top', rotation=90)
    fig.text(1, 0.8, "Temp (C)", ha='right', va='top', rotation=-90)

    return fig, co2_axes, temp_axes


def plot_co2(ax, unit_readings, co2_col=None):

    px_size_pts = 72.0 / ax.get_figure().dpi

    # Draw co2 line
    ax.plot(unit_readings.datetime, unit_readings[co2_col],
            linewidth=2*px_size_pts, zorder=2)

    # Draw co2 fill
    ax.fill_between(unit_readings.datetime, -1000000, unit_readings[co2_col],
            alpha=0.3)


def plot_temp(ax, unit_readings):

    # This plot requires making segments between pairs of temps.
    # If there is only one reading it will not work.
    if len(unit_readings) < 2:
        return

    px_size_pts = 72.0 / ax.get_figure().dpi

    # Use multi-colored line technique from:
    # https://matplotlib.org/3.1.1/gallery/lines_bars_and_markers/multicolored_line.html
    #
    # Instead of a line, turn the list of points into a collection of
    # segments from each point to the next. Then give each segment a
    # separate color.

    # Colormap for temperature
    cmap = mpl.colors.LinearSegmentedColormap.from_list("coolblackwarm",
            ['blue','black','red'])
    norm = mpl.colors.Normalize(-5, 5, clip=True)

    # First convert dates to numbers
    numericdates = mpl.dates.date2num(unit_readings.datetime)

    # Create a list of points
    # [[date0, temp0], [date1,temp1], ...]
    pts = np.array([numericdates, unit_readings.temp]).T

    # Reshape to list of 1-element list of points (-1 means infer size)
    # [ [[date0,temp0]], [[date1,temp1]], ...]
    pts = pts.reshape(-1, 1, 2)

    # Copy, shift, and concatenate on the second axis to get a list of two-point line segments
    # [ [[date0,temp0],[date1,temp1]], [[date1,temp1],[date2,temp2]], ...]
    segments = np.concatenate([pts[:-1], pts[1:]], axis=1)

    # Create a LineCollection from segments (each segment is one line in the collection)
    lc = mpl.collections.LineCollection(segments, cmap=cmap, norm=norm)

    segment_avg_temps = (unit_readings.temp[:-1] + unit_readings.temp[1:]) / 2
    lc.set_array(segment_avg_temps)
    lc.set_linewidth(2*px_size_pts)
    line = ax.add_collection(lc)


def mark_deployment(ax, deploy):

    px_size_pts = 72.0 / ax.get_figure().dpi
    ymax = 2000 * 1000 * 1000       # 200% co2
    ymin = -10 * 1000

    x = deploy.deploy_date
    if not pd.isnull(deploy.bring_back_date):
        x = [x, deploy.bring_back_date]

    # Draw deploy start line
    ax.vlines(x, ymin, ymax,
                linewidth = 4 * px_size_pts,
                linestyles = 'solid',
                color = 'black',
                zorder = 1)

def write_site_label(ax, site_label):

    t = ax.text(0.01, 0.85, site_label, transform=ax.transAxes,
                horizontalalignment='left', verticalalignment='top',
                fontsize='x-small',
                zorder=10)
    t.set_bbox(dict(facecolor='ghostwhite', alpha=0.8, edgecolor='lightgrey'))


def plot_co2_and_temp_by_site(co2s, deploys, co2_col="co2_mean", same_range_co2=None, same_range_temp=None, dpi=96):

    # Get site names from data
    # Use that to set the number of plots
    sites = co2s.loc[~co2s.site.isnull()].site.unique()
    sites = sorted(list(sites))

    fig, co2_axes, temp_axes = set_up_axes(co2s, sites=sites,
            co2_col=co2_col, same_range_co2=same_range_co2, same_range_temp=same_range_temp, dpi=dpi)

    for i, site in enumerate(reversed(sites)):

        site_readings = co2s.loc[co2s.site == site]
        site_deploys = deploys.loc[deploys.site == site].sort_values(by="deploy_date")

        # Iterate over deployments and draw co2 plots
        for j, deploy in site_deploys.iterrows():

            unit_readings_select = site_readings.unit_id == deploy.unit_id
            unit_readings_select &= site_readings.datetime >= deploy.deploy_date
            if not pd.isnull(deploy.bring_back_date):
                unit_readings_select &= site_readings.datetime <= deploy.bring_back_date

            unit_readings = site_readings.loc[unit_readings_select]

            plot_co2(co2_axes[i], unit_readings, co2_col=co2_col)
            plot_temp(temp_axes[i], unit_readings)
            mark_deployment(co2_axes[i], deploy)

        # Draw site label on the temperature axis because it's on top
        write_site_label(temp_axes[i], site)

    return fig, co2_axes

if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Plot CO2 data")
    parser.add_argument('--dpi', type=int, default="96")
    parser.add_argument('--recent-days', type=int, default=None)
    parser.add_argument('--same-ranges', action='store_true')
    parser.add_argument('--co2-max', type=int, default=None)
    parser.add_argument('dbfile', type=str)
    parser.add_argument('plotfile', type=str)

    args = parser.parse_args()

    db = sqlite3.connect(args.dbfile)
    co2_readings = fetch_co2_data(db)
    co2_readings = filter_bad_values(co2_readings)
    deploys = fetch_deploy_data(db)

    co2_readings = add_co2_std_column(co2_readings)

    if args.recent_days:
        date_cutoff = pd.Timestamp.now() - pd.Timedelta(days=args.recent_days)
        co2_readings = co2_readings[co2_readings.datetime > date_cutoff]

    kwargs = {}

    kwargs['dpi'] = args.dpi

    if args.same_ranges:
        kwargs['same_range_co2'] = True
        kwargs['same_range_temp'] = (-40, 30)

    if args.co2_max:
        kwargs['same_range_co2'] = (0, args.co2_max)

    fig, ax = plot_co2_and_temp_by_site(co2_readings, deploys, **kwargs)
    plt.tight_layout(h_pad=0.3)

    plt.savefig(args.plotfile)
