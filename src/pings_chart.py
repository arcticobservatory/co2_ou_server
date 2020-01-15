import pandas as pd
import numpy as np

# MatPlotLib (for generating ping chart)
#=================================================================

import matplotlib as mpl
import matplotlib.pyplot as plt

# Use a colorblind-friendly palette
plt.style.use('tableau-colorblind10')

# Explicitly register Pandas date converters for MatPlotLib
# Pandas warns us if we don't
pd.plotting.register_matplotlib_converters()

def generate_pings_chart(db):
    # Get deploy info
    deploys_sql = """
    select
        *,
        null as nickname,
        null as bring_back_date
    from deploy
    where
        site is not null
    """
    deploys = pd.read_sql(deploys_sql, db, parse_dates=['deploy_date','bring_back_date'])

    # Get deploy pings
    deploy_pings_sql = """
    select
            p.ping_date,
            p.ping_time,
            d.site,
            p.unit_id,
            p.nickname,
            rssi_raw,
            rssi_dbm
    from deploy d
    left join pings p
            on p.unit_id = d.unit_id
            and p.ping_date > d.deploy_date
    where
        d.site is not null
            and ping_date is not null
    order by
            ping_date,
            site desc,
            deploy_date
    ;
    """
    deploy_pings = pd.read_sql(deploy_pings_sql, db, parse_dates=['ping_date'])

    first_deploy = deploys.deploy_date.min()
    last_bring_back = deploys.bring_back_date.max()
    today = pd.Timestamp.now().normalize()
    any_still_deployed = pd.isnull(deploys.bring_back_date).any()

    sites = sorted(list(deploys.site.unique()))

    fig, ax = plt.subplots()

    # Some parameters we will reuse
    bar_width = 0.5
    deploy_line_height = .8
    deploy_line_style = 'solid'
    day_width = pd.Timedelta(days=1.1)
    day_offset = -pd.Timedelta(days=0) #day_width/2)

    # Set x axis limits
    # This also tells MatPlotLib that the x axis will be dates,
    # so we don't get errors when we try to draw date values on the x axis
    daymax = today if any_still_deployed else last_bring_back
    plt.xlim(first_deploy + day_offset, daymax + day_width)

    # Iterate over deployment sites

    yvals = []      # Save y values for labels later
    nicknames = []  # Save nicknames for labels later

    for i, site in enumerate(sites):
        # Save y value for tick labels later
        yval = i+1
        yvals.append(yval)

        # Separate pings for just this site, and draw a broken bar graph
        site_pings = deploy_pings.loc[deploy_pings.site == site].sort_values(by="ping_date")
        date_tuples = [(ping_date + day_offset, day_width) for ping_date in site_pings.ping_date]
        ax.broken_barh(date_tuples, (yval-bar_width/2, bar_width))

        # Separate deploy durations for just this site
        # and draw lines representing deployment
        site_deploys = deploys.loc[deploys.site==site].sort_values(by="deploy_date")

        for j, row in site_deploys.iterrows():
            still_out = pd.isnull(row.bring_back_date)
            deploy_start = row.deploy_date
            deploy_end = (row.bring_back_date if not still_out else today)

            # Pings are in the early morning
            # Deployment is in the afternoon
            # So we want to draw the dividing line where the end of the day's bar would be
            deploy_start += day_offset + day_width
            deploy_end   += day_offset + day_width

            # Draw deploy lines
            plt.vlines(deploy_start, yval-deploy_line_height/2, yval+deploy_line_height/2, linestyles=deploy_line_style)
            plt.hlines(yval, deploy_start, deploy_end, linestyles=deploy_line_style)
            if not still_out:
                plt.vlines(deploy_end, yval-deploy_line_height/2, yval+deploy_line_height/2, linestyles=deploy_line_style)

        # Save nickname for tick labels later
        if not site_pings.empty:
            nicknames.append(site_pings.nickname.iloc[-1])
        elif not site_deploys.empty:
            nicknames.append(site_deploys.nickname.iloc[-1])
        else:
            nicknames.append(None)

    plt.grid(True)

    # Format x axis
    major_locator = mpl.dates.AutoDateLocator()
    minor_locator = mpl.dates.DayLocator()
    ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_minor_locator(minor_locator)
    ax.xaxis.set_major_formatter(mpl.dates.ConciseDateFormatter(major_locator))
    plt.xticks(rotation=60)

    # Format y axis
    plt.ylabel("site")
    plt.yticks(yvals, sites)
    plt.ylim(min(yvals)-0.5, max(yvals)+0.5)

    ymin, ymax = plt.ylim()

    # Create a second y axis for unit nicknames
    par1 = ax.twinx()
    par1.set_ylim(ymin,ymax)
    par1.set_yticks(yvals)
    par1.set_yticklabels(nicknames)
    par1.set_ylabel("unit nickname")

    # Make the plot paper page width
    fig.set_size_inches(11,4)

    plt.tight_layout()

    return plt
