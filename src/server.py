#!/usr/bin/env/python3

import argparse
import datetime
import logging
import os
import subprocess

import flask
import flask_restful

import seqfile

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

# Main
#=================================================================

if __name__ == "__main__":
    parser = build_parser();
    args = parser.parse_args();
    app.run(host='0.0.0.0', port=args.port, debug=True)
