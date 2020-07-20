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

def fetch_ping_data(db):
    # Get deploy pings
    pings_sql = """
    select
            p.ping_ts,
            p.ping_date,
            p.ping_time,
            d.site,
            p.unit_id,
            p.nickname,
            rssi_raw,
            rssi_dbm
    from pings p
    left join deploy_durations d
            on p.unit_id = d.unit_id
            and p.ping_ts >= d.deploy_date
            and (d.bring_back_date is null or p.ping_ts <= d.bring_back_date)
    order by
            ping_ts,
            site desc,
            deploy_date
    ;
    """
    pings = pd.read_sql(pings_sql, db, parse_dates=['ping_ts','ping_date','ping_time'])
    return pings

def fetch_deploy_data(db):
    deploys = pd.read_sql('select * from deploy_durations', db, parse_dates=['deploy_date','bring_back_date'])
    return deploys

def plot_pings(pings, deploys, xmin=None, xmax=None):

    # Create figure/axes
    fig, ax = plt.subplots()

    # Some parameters we will reuse
    deploy_line_height = .8
    deploy_line_style = 'solid'

    # Method to translate a ping timestamp to a box on the plot
    # (Fill the whole day, plus a little to overlap)
    ping_bar_height = 0.5
    ping_bar_width = pd.Timedelta(days=1.1)

    def ping_bar_start(ping_ts): return ping_ts.normalize()
    def ping_bar_end(ping_ts): return ping_bar_start(ping_ts) + ping_bar_width

    # Determine and set x axis limits
    #
    # We need to set x limits ahead of time to give Matplotlib a heads-up that
    # this axis will be pd.Timestamp values.
    # Otherwise we will get errors when we try to draw date values on the axis.

    deploy_min = deploys.deploy_date.min()
    deploy_max = deploys.bring_back_date.max()

    if pd.isnull(deploys.deploy_date).any():
        deploy_min = pings.ping_ts.min()

    if pd.isnull(deploys.bring_back_date).any():
        deploy_max = pd.Timestamp.now()

    if not xmin:
        xmin = ping_bar_start(deploy_min)
    else:
        xmin = ping_bar_start(pd.Timestamp(xmin))

    if not xmax:
        xmax = ping_bar_end(deploy_max)
    else:
        xmax = ping_bar_end(pd.Timestamp(xmax))

    # print("xmin", xmin, "xmax", xmax)
    xmargin = (xmax - xmin) * 0.005

    plt.xlim(xmin - xmargin, xmax + xmargin)

    # Create arrays to gather left/right tick labels (site names and unit nicknames)
    yvals = []
    left_tick_labels = []
    right_ticks_labels = []

    # Iterate over deployment sites as rows

    sites = sorted(list(deploys.site.unique()))

    for i, site in enumerate(sites):

        # Select all deployments for this site/row
        site_deploys = deploys.loc[deploys.site==site].sort_values(by="bring_back_date", na_position='last')

        # Determine y value and left/right y axis labels for row
        yval = i+1
        yvals.append(yval)
        left_tick_labels.append(site)

        if not site_deploys.empty:
            right_ticks_labels.append(site_deploys.nickname.iloc[-1])
        else:
            right_ticks_labels.append(None)

        # Iterate over site deployments as segments within the row

        for j, deploy in site_deploys.iterrows():
            # print('deploy', deploy)

            # Determine deploy segment start and end
            deploy_start = (deploy.deploy_date if not pd.isnull(deploy.deploy_date) else xmin)
            deploy_end = (deploy.bring_back_date if not pd.isnull(deploy.bring_back_date) else xmax)

            # Select pings in the deployment
            unit_pings_select = pings.site == deploy.site
            unit_pings_select &= pings.unit_id == deploy.unit_id
            unit_pings_select &= pings.ping_ts >= deploy_start
            unit_pings_select &= pings.ping_ts <= deploy_end
            unit_pings = pings.loc[unit_pings_select]

            # Determine ping bar placement
            ping_bars = []
            for ping_ts in unit_pings.ping_ts:
                bar_start = max(ping_bar_start(ping_ts), deploy_start)
                bar_end = min(ping_bar_end(ping_ts), deploy_end)
                ping_bar = (bar_start, bar_end-bar_start)
                ping_bars.append(ping_bar)

            # Remove redundant bars (multiple pings in same period)
            ping_bars = pd.Series(ping_bars).unique()

            # Draw ping bars
            ax.broken_barh(ping_bars, (yval-ping_bar_height/2, ping_bar_height))

            # Draw deploy lines
            if not pd.isnull(deploy.deploy_date):
                plt.vlines(deploy.deploy_date, yval-deploy_line_height/2, yval+deploy_line_height/2, linestyles=deploy_line_style)
            plt.hlines(yval, deploy_start, deploy_end, linestyles=deploy_line_style)
            if not pd.isnull(deploy.bring_back_date):
                plt.vlines(deploy.bring_back_date, yval-deploy_line_height/2, yval+deploy_line_height/2, linestyles=deploy_line_style)

    plt.grid(True)

    # Format x axis
    major_locator = mpl.dates.AutoDateLocator()
    minor_locator = mpl.dates.DayLocator(bymonthday=[1,8,15,22,29])
    ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_minor_locator(minor_locator)
    ax.xaxis.set_major_formatter(mpl.dates.ConciseDateFormatter(major_locator))
    #plt.xticks(rotation=60)

    # Format y axis
    ymargin = 0.5
    ymin = min(yvals) - ymargin
    ymax = max(yvals) + ymargin

    # Format left y axis
    ax.set_ylim(ymin,ymax)
    ax.set_yticks(yvals)
    ax.set_ylabel("Deployment Site")
    ax.set_yticklabels(left_tick_labels)

    # Create a right-hand y axis for secondary info (unit nicknames)
    ax2 = ax.twinx()
    ax2.set_ylim(ymin,ymax)
    ax2.set_yticks(yvals)
    ax2.set_ylabel("unit nickname")
    ax2.set_yticklabels(right_ticks_labels)

    # Set figure size
    fig.set_size_inches(11,4)
    plt.tight_layout()

    return fig, ax, ax2

if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Plot pings data")
    parser.add_argument('dbfile', type=str)
    parser.add_argument('plotfile', type=str)
    parser.add_argument('--xmin', type=str, required=False, default=None)
    parser.add_argument('--xmax', type=str, required=False, default=None)
    parser.add_argument("--site-contains", type=str, required=False, default=None)
    parser.add_argument("--right-axis-label", type=str, required=False, default=None)
    parser.add_argument("--right-axis-map", type=str, required=False, default=None)
    parser.add_argument("--title", type=str, required=False, default=None)

    args = parser.parse_args()

    db = sqlite3.connect(args.dbfile)
    pings = fetch_ping_data(db)
    deploys = fetch_deploy_data(db)

    if args.site_contains:
        deploys = deploys[deploys['site'].str.contains(args.site_contains)]

    fig, ax, ax2 = plot_pings(pings, deploys, xmin=args.xmin, xmax=args.xmax)

    if args.right_axis_label:
        ax2.set_ylabel(args.right_axis_label)
        plt.tight_layout()

    if args.right_axis_map:
        import json
        axmap = json.loads(args.right_axis_map)
        left_labels = [textobj.get_text() for textobj in ax.get_yticklabels()]
        right_labels = [axmap[left] for left in left_labels]
        ax2.set_yticklabels(right_labels)
        plt.tight_layout()

    if args.title:
        ax.set_title(args.title)
        plt.tight_layout()

    plt.savefig(args.plotfile)
