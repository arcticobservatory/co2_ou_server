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

def fetch_deploy_data(db):
    deploys = pd.read_sql('select * from deploy_durations', db, parse_dates=['deploy_date','bring_back_date'])
    return deploys

def plot_co2_and_temp_by_site(co2s, deploys, co2_col="co2_mean", same_range_co2=None, same_range_temp=None, dpi=96):
    # We will add a co2_mean column later.
    # For now we will plot with in a regular column like "co2_05".

    # Get site names from data
    # Use that as number of plots
    sites = co2s.loc[~co2s.site.isnull()].site.unique()
    sites = sorted(list(sites))

    fig, ax = plt.subplots(nrows=len(sites), ncols=1, sharex=True)
    fig.dpi = dpi

    # Set page size
    ## 8in x 10in for 15 subplots
    fig.set_size_inches(8.0, 10.0 * (len(sites)/15.0))

    # Some parameters we will reuse

    ## Pixel size in points, so we can specify very thin lines
    ## dots per inch / 72.0 pts per inch = pts per dot
    px_size_pts = 72.0 / fig.dpi

    ## Marker size for scatter plots (s) is measured in marker AREA in pts squared,
    ## so we need to square the width.
    ## However, if s is less than 1 you get strange effects
    ## (point markers change from '.' to unfilled circles),
    ## so we need to make sure the area is at least 1.
    scattersize_pts_sq = max(px_size_pts**2, 1)

    # How to draw deploy lines
    deploy_line_style = 'solid'

    # Set x axis limits
    # This also tells MatPlotLib that the x axis will be dates,
    # so we don't get errors when we try to draw date values on the x axis
    xmin = co2s.datetime.min()
    xmax = co2s.datetime.max()
    plt.xlim(xmin, xmax)

    for i, site in enumerate(reversed(sites)):

        site_readings = co2s.loc[co2s.site == site]
        site_deploys = deploys.loc[deploys.site == site].sort_values(by="deploy_date")

        margin = 0.05

        # Get axis for co2 plot
        co2_ax = ax[i]

        if isinstance(same_range_co2, tuple):
            co2_min, co2_max = same_range_co2
            co2_ax.set_ylim([co2_min, co2_max])
        elif same_range_co2 == True:
            co2_min = co2s[co2_col].min()
            co2_max = co2s[co2_col].max()
            co2_min -= margin * (co2_max - co2_min)
            co2_max += margin * (co2_max - co2_min)
            co2_ax.set_ylim([co2_min, co2_max])
        else:
            co2_min = site_readings[co2_col].min()
            co2_max = site_readings[co2_col].max()
            co2_min -= margin * (co2_max - co2_min)
            co2_max += margin * (co2_max - co2_min)

        # Create an axis for temperature
        temp_ax = co2_ax.twinx()

        if isinstance(same_range_temp, tuple):
            t_min, t_max = same_range_temp
            temp_ax.set_ylim([t_min, t_max])
        elif same_range_temp == True:
            t_min = co2s.temp.min()
            t_max = co2s.temp.max()
            t_min -= margin * (t_max - t_min)
            t_max += margin * (t_max - t_min)
            temp_ax.set_ylim([t_min, t_max])

        # Format y axes
        for _ax in [co2_ax,temp_ax]:
            _ax.yaxis.set_major_locator(mpl.ticker.AutoLocator())
            _ax.yaxis.set_minor_locator(mpl.ticker.AutoMinorLocator())
            _ax.tick_params(axis = 'both', which = 'major', labelsize = 'x-small')

        # Iterate over deployments and draw co2 plots
        for j, deploy in site_deploys.iterrows():

            unit_readings_select = site_readings.unit_id == deploy.unit_id
            unit_readings_select &= site_readings.datetime >= deploy.deploy_date
            if not pd.isnull(deploy.bring_back_date):
                unit_readings_select &= site_readings.datetime <= deploy.bring_back_date

            unit_readings = site_readings.loc[unit_readings_select]

            # Draw co2 line
            co2_ax.plot(unit_readings.datetime, unit_readings[co2_col], label=deploy.unit_id,
                    linewidth=2*px_size_pts, zorder=2)

            # Draw co2 fill
            co2_ax.fill_between(unit_readings.datetime, max(co2_min,0), unit_readings[co2_col],
                    alpha=0.3)

            # Draw temperature

            ## Calculate temperature colormap red--blue
            reddest, bluest = 30, -30
            tc = (unit_readings.temp-bluest)/(reddest-bluest)

            ## Draw temperature scatterplot
            temp_ax.scatter(unit_readings.datetime, unit_readings.temp, label=deploy.unit_id,
                    c=mpl.cm.coolwarm(tc.clip(0,1)),
                    marker='.', s=scattersize_pts_sq, zorder=1)

            # Draw deploy start line
            co2_ax.vlines(deploy.deploy_date, co2_min, co2_max,
                        linewidth=2*px_size_pts, linestyles=deploy_line_style, color='lightgrey', zorder=1)

            # Draw deploy end line
            if not pd.isnull(deploy.bring_back_date):
                co2_ax.vlines(deploy.bring_back_date, co2_min, co2_max,
                        linewidth=2*px_size_pts, linestyles=deploy_line_style, color='lightgrey', zorder=1)

        # Draw plot label
        ## Draw it on the temperature ax because that axis is on top
        t = temp_ax.text(0.01, 0.85, site, transform=co2_ax.transAxes,
                    horizontalalignment='left', verticalalignment='top', fontsize='x-small', zorder=10)
        t.set_bbox(dict(facecolor='ghostwhite', alpha=0.8, edgecolor='lightgrey'))

    # Format x axis
    major_locator = mpl.dates.AutoDateLocator()
    if xmax - xmin <= pd.Timedelta(days=31):
        minor_locator = mpl.dates.HourLocator(byhour=[0,8,16])
    else:
        minor_locator = mpl.dates.DayLocator(bymonthday=[1,8,15,22,29])
    ax[0].xaxis.set_major_locator(major_locator)
    ax[0].xaxis.set_minor_locator(minor_locator)
    ax[0].xaxis.set_major_formatter(mpl.dates.ConciseDateFormatter(major_locator))

    plt.tight_layout(h_pad=0.3)
    return fig, ax

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
        margin = 0.05
        kwargs['same_range_co2'] = (0 - margin*args.co2_max, args.co2_max + margin*args.co2_max)

    fig, ax = plot_co2_and_temp_by_site(co2_readings, deploys, **kwargs)

    plt.savefig(args.plotfile)
