#!/usr/bin/env/python3

import argparse
import datetime
import logging
import os

import flask
import flask_restful

import seqfile

# Command-Line Argument Parsing
#=================================================================

def build_parser():
    parser = argparse.ArgumentParser(prog=__file__)

    parser.add_argument("-p", "--port", type=int, default=80,
            help="Port number to listen on.")

    parser.add_argument("--shutdown-grace-seconds", type=float, default=2,
            help="When server is asked to shutdown, give it this many seconds to shutdown cleanly.")

    parser.add_argument("--loglevel", default="INFO",
            help="Logging level. ERROR, WARN, INFO, DEBUG.")

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

class HelloWorld(flask_restful.Resource):
    def get(self):
        return "Hello world!"

class OuAlive(flask_restful.Resource):
    def post(self, ou_id):
        var_dir = flask.current_app.config["SERVER_VAR_DIR"]
        alive_dir = flask.safe_join(var_dir, "pings")
        target = prep_append_file(dir=alive_dir, match=("pings-", ".tsv"))
        tiso = datetime.datetime.utcnow().isoformat()
        row = [tiso, ou_id]
        with open(target, "at") as f:
            f.write("\t".join(row))
            f.write("\n")
        return None

class OuPush(flask_restful.Resource):
    def get(self, ou_id, filepath):
        print(flask.request)
        print(flask.request.data)

    def put(self, ou_id, filepath):
        data_dir = flask.current_app.config["OU_DATA_DIR"]
        data = flask.request.data
        offset = int(flask.request.args["offset"])

        localpath = flask.safe_join(data_dir, ou_id, filepath)
        os.makedirs(os.path.dirname(localpath), exist_ok=True)

        with open(localpath, "a+b") as f:
            # Note: seeking past the end of the file and then writing will fill the gap with zeros
            f.seek(offset)
            f.write(data)

# Main
#=================================================================

if __name__ == "__main__":
    app = flask.Flask(__name__)
    app.config['OU_DATA_DIR'] = "remote_data"
    app.config['SERVER_VAR_DIR'] = "var"

    api = flask_restful.Api(app)
    api.add_resource(HelloWorld, "/")
    api.add_resource(OuAlive, "/ou/<string:ou_id>/alive")
    api.add_resource(OuPush, "/ou/<string:ou_id>/push-sequential/<path:filepath>")

    app.run(host='0.0.0.0', port=8080, debug=True)
