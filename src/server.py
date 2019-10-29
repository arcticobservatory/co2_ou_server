#!/usr/bin/env/python3

import argparse
import datetime
import io
import logging
import os
import sqlite3
import subprocess
import time

import flask
import flask_restful
import json2table
import pandas as pd
import numpy as np

import seqfile

# MatPlotLib (for generating ping chart)
#=================================================================

import matplotlib as mpl
import matplotlib.pyplot as plt

# Use a colorblind-friendly palette
plt.style.use('tableau-colorblind10')

# Explicitly register Pandas date converters for MatPlotLib
# Pandas warns us if we don't
pd.plotting.register_matplotlib_converters()

# Command-Line Argument Parsing
#=================================================================

def build_parser():
    parser = argparse.ArgumentParser(prog=__file__)

    parser.add_argument("-p", "--port", type=int, default=8080,
            help="Port number to listen on.")

    return parser

# Helpers
#=================================================================

def prep_append_file(dir=".", match=('',''), size_limit=100*1024):
    os.makedirs(dir, exist_ok=True)
    target = seqfile.choose_append_file(dir, match, size_limit)
    tpath = "/".join([dir, target])
    return tpath

# Flask
#=================================================================
# Flash-Restful docs index:             https://flask-restful.readthedocs.io/en/latest/index.html
# URL path patterns:                    https://flask.palletsprojects.com/en/1.1.x/api/#url-route-registrations
# Flask-Restful request parsing helper: https://flask-restful.readthedocs.io/en/latest/reqparse.html
# Flask's lower-level request parsing:  https://flask.palletsprojects.com/en/1.1.x/api/#flask.Request
# Flask Requests file handling:         https://flask.palletsprojects.com/en/1.1.x/api/#flask.Request.files
# RFC for multipart form data:          https://tools.ietf.org/html/rfc2388
# Curl multipart form posts:            https://ec.haxx.se/http-multipart.html
# Werkzeug's filename sanitizer:        https://werkzeug.palletsprojects.com/en/0.15.x/utils/#werkzeug.utils.secure_filename

app = flask.Flask(__name__)
app.config['REMOTE_DATA_DIR'] = "../remote_data"
app.config['SERVER_VAR_DIR'] = "../var"
app.config['DB_PATH'] = "../var/db.sqlite3"
app.config['PINGS_CHART_NAME'] = "pings_chart.svg"
app.config['PINGS_CHART_PATH'] = "../var/pings_chart.svg"
app.config['PINGS_CHART_TMP_PATH'] = "../var/pings_chart_tmp.svg"

class HelloWorld(flask_restful.Resource):
    def get(self):
        return "Hello world!"

class OuAlive(flask_restful.Resource):
    def post(self, ou_id):
        args = flask.request.args
        tiso = datetime.datetime.utcnow().isoformat()

        row = [tiso, ou_id]
        for i,a in enumerate(["site_code", "rssi_raw", "rssi_dbm"]):
            val = args[a] if a in args else None
            row.append(str(val))

        var_dir = flask.current_app.config["SERVER_VAR_DIR"]
        alive_dir = flask.safe_join(var_dir, "pings")
        target = prep_append_file(dir=alive_dir, match=("pings-", ".tsv"))
        with open(target, "at") as f:
            f.write("\t".join(row))
            f.write("\n")

        try:
            sqlrow = {
                    "ping_date": tiso[:len("2019-09-17")],
                    "ping_time": tiso[len("2019-09-17T"):],
                    "unit_id": ou_id,
                    "nickname": args["site_code"] if "site_code" in args else None,
                    "rssi_raw": args["rssi_raw"] if "rssi_raw" in args else None,
                    "rssi_dbm": args["rssi_dbm"] if "rssi_dbm" in args else None,
            }
            db_path = flask.current_app.config["DB_PATH"]
            db = sqlite3.connect(db_path)
            with db:
                db.execute("insert into pings values (:ping_date, :ping_time, :unit_id, :nickname, :rssi_raw, :rssi_dbm);", sqlrow)
            db.close()
        except Exception as e:
            print("Could not add ping to database:", e)

        return {}

class StatusAliveRecent(flask_restful.Resource):
    def get(self):
        var_dir = flask.current_app.config["SERVER_VAR_DIR"]
        alive_dir = flask.safe_join(var_dir, "pings")
        dirlist = sorted(os.listdir(alive_dir))
        target = seqfile.last_file_in_sequence(dirlist, match=("pings-", ".tsv"))
        target = flask.safe_join(alive_dir, target)
        if not target:
            return "No recent pings"
        else:
            args = flask.request.args
            asc = args["asc"] in ["true","True","1"] if "asc" in args else False
            refresh = args["refresh"] if "refresh" in args else None

            tailproc = subprocess.run(["tail", "-n", "20", target], stdout=subprocess.PIPE)
            lines = tailproc.stdout.decode("utf-8").strip().split("\n")

            tiso = datetime.datetime.utcnow().isoformat()
            lines.append("{}\t(now)".format(tiso))

            if not asc:
                lines = list(reversed(lines))

            for i,line in enumerate(lines):
                # Strip sub-seconds from timestampe
                line = line[:len("2019-09-17T16:37:12")] + line[len("2019-09-17T16:37:12.455629"):]
                # Strip "co2unit-" part
                line = line.replace("\tco2unit-", "\t")
                lines[i] = line

            resp = flask.Response("\n".join(lines), mimetype="text/plain")

            if refresh:
                try:
                    refresh = int(refresh)
                    resp.headers["Refresh"] = refresh
                except:
                    pass

            return resp

html_style = """
    <style type="text/css">
        table {
            font-family: "Verdana", sans-serif;
            border-collapse: collapse;
            text-align: right;
            font-size: 10pt;
        }
        th {
            font-weight: normal;
        }
        td {
            padding: .2em .5em;
        }
        table tr:nth-child(even) {
          background: #ddd;
        }
    </style>
"""

class StatusAliveSummary(flask_restful.Resource):
    def get(self):
        var_dir = flask.current_app.config["SERVER_VAR_DIR"]
        chart_name = flask.current_app.config["PINGS_CHART_NAME"]
        db_path = flask.current_app.config["DB_PATH"]
        db = sqlite3.connect(db_path)
        cur = db.execute("SELECT * FROM pings_by_unit_id;")

        rows = cur.fetchall()
        col_names = [column[0] for column in cur.description]
        df = pd.DataFrame.from_records(data=rows, columns=col_names)
        db.close()

        # Massage data
        intfmt = lambda n: str(int(n)) if n==n else ''
        df.deploy_days = df.deploy_days.apply(intfmt)
        df.deploy_ping_days = df.deploy_ping_days.apply(intfmt)
        df = df.replace(np.nan, '')

        # html = df.to_html(border=0)
        html = df.to_html(
                border = 0,
                justify = "right",
                na_rep = "",
                float_format = lambda n: "{:.1f}".format(n) if n==n else "",
                )

        html = """
            {style}
            <img src="{chart_name}" alt="pings chart"/>
            <center>
                <br/><br/>
            </center>
            {table}
        """.format(style=html_style, chart_name=chart_name, table=html)

        resp = flask.Response(html_style + html, mimetype="text/html")
        resp.headers["Refresh"] = str(10 * 60)

        # print(list(rows))
        return resp

class StatusAliveChart(flask_restful.Resource):
    def get(self):
        logger = flask.current_app.logger
        var_dir = flask.current_app.config["SERVER_VAR_DIR"]
        chart_path = flask.current_app.config["PINGS_CHART_PATH"]
        chart_tmp_path = flask.current_app.config["PINGS_CHART_TMP_PATH"]
        chart_ttl = 10 * 60
        chart_build_timeout = 2
        chart_refresh = time.time() - chart_ttl

        def serve_chart_file():
            logger.debug("pings_chart: serving %s", chart_path)
            return flask.send_file(chart_path, cache_timeout=chart_ttl)

        if os.path.isfile(chart_path) and os.path.getmtime(chart_path) > chart_refresh:
            return serve_chart_file()

        import pathlib

        wait_start = time.time()
        if os.path.isfile(chart_tmp_path):
            logger.info("pings_chart: temp file is present. Waiting for other process to build chart. %s", chart_tmp_path)
            while True:
                time.sleep(.1)
                if not os.path.isfile(chart_tmp_path) and os.path.isfile(chart_path):
                    logger.info("pings_chart: temp file is gone. Chart is finished, serving. %s", chart_tmp_path)
                    return serve_chart_file()
                if time.time() > wait_start + chart_build_timeout:
                    logger.warn("pings_chart: timeout waiting for other process. Building chart myself. %s", chart_tmp_path)
                    break

        # Touch the temp file to claim it
        logger.info("pings_chart: claiming temp file. %s", chart_tmp_path)
        pathlib.Path(chart_tmp_path).touch()

        # Delay for testing
        # time.sleep(5)

        logger.debug("pings_chart: building chart")

        db_path = flask.current_app.config["DB_PATH"]
        db = sqlite3.connect(db_path)

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
        logger.debug("pings_chart: done building, saving to temp file. %s", chart_tmp_path)
        plt.savefig(chart_tmp_path)

        # Move the temp file into place
        logger.info("pings_chart: done. Moving temp file into place. %s", chart_path)
        os.rename(chart_tmp_path, chart_path)

        return serve_chart_file()

def sequential_dir_progress(localdir):
    files = os.listdir(localdir)
    files.sort()
    lastfile = seqfile.last_file_in_sequence(files)
    if lastfile:
        lastpath = flask.safe_join(localdir, lastfile)
        size = os.stat(lastpath)[6]
        return [lastfile, size]
    else:
        return [None, None]

class OuPush(flask_restful.Resource):
    def get(self, ou_id, filepath):
        print(flask.request)
        print(flask.request.data)

    def put(self, ou_id, filepath):
        data_dir = flask.current_app.config["REMOTE_DATA_DIR"]
        data = flask.request.data
        offset = int(flask.request.args["offset"])

        localpath = flask.safe_join(data_dir, ou_id, filepath)
        localdir = os.path.dirname(localpath)
        localfile = os.path.basename(localpath)

        # Make sure everything exists
        os.makedirs(localdir, exist_ok=True)
        if not os.path.isfile(localpath):
            with open(localpath, "w"):
                pass

        # Make sure we're not skipping part of a file
        lastfile, lastsize = sequential_dir_progress(localdir)
        if lastfile == localfile and offset > lastsize + 1:
            return {
                    "error": "SKIPPED_PART_OF_FILE",
                    "ack_file": [lastfile, lastsize, lastsize],
                    }, 416

        # On file modes:
        #
        # a will force append to the end of the file.
        # w will truncate the file.
        # r+ allows reading and seeking.
        #
        # So r+ is what we need, but it throws an error if the file doesn't
        # exist, so create it first.

        with open(localpath, "r+b") as f:
            # Note: seeking past the end of the file and then writing will fill the gap with zeros
            f.seek(offset)
            f.write(data)

        lastfile, lastsize = sequential_dir_progress(localdir)
        return {
                "ack_file": [lastfile, lastsize, lastsize],
            }

def find_files(topdir):
    for dpath, dirnames, fnames in os.walk(topdir):
        for fname in fnames:
            yield "/".join([dpath,fname])

def strip_prefix(prefix, str_iter):
    for s in str_iter:
        if not s.startswith(prefix):
            raise Exception("No prefix: {} does not start with {}".format(s, prefix))
        yield s[len(prefix):]

class OuPull(flask_restful.Resource):
    def get(self, ou_id, filepath):
        data_dir = flask.current_app.config["REMOTE_DATA_DIR"]
        localpath = flask.safe_join(data_dir, ou_id, filepath)
        args = flask.request.args
        recursive = "recursive" in args and args["recursive"] in ["True", "1"]

        if not filepath: flask.abort(404)

        firstsegment = filepath.split("/")[0]
        whitelist = ["updates"]

        if not firstsegment in whitelist: flask.abort(404)

        if os.path.isdir(localpath):
            if not recursive:
                return os.listdir(localpath)
            else:
                prefix = localpath + "/"
                fpaths = strip_prefix(prefix, find_files(localpath))
                return list(fpaths)

        elif os.path.isfile(localpath):
            fname = os.path.basename(localpath)
            f = open(localpath, "rb")
            return flask.send_file(f, attachment_filename=fname)

        else:
            flask.abort(404)

api = flask_restful.Api(app)
api.add_resource(HelloWorld, "/")
api.add_resource(OuAlive, "/ou/<string:ou_id>/alive")
api.add_resource(OuPush, "/ou/<string:ou_id>/push-sequential/<path:filepath>")
api.add_resource(OuPull, "/ou/<string:ou_id>/<path:filepath>")
api.add_resource(StatusAliveRecent, "/status/alive/recent")
api.add_resource(StatusAliveSummary, "/status/alive/summary")
api.add_resource(StatusAliveChart, "/status/alive/" + app.config["PINGS_CHART_NAME"])

# Main
#=================================================================

if __name__ == "__main__":
    parser = build_parser();
    args = parser.parse_args();
    app.run(host='0.0.0.0', port=args.port, debug=True)
