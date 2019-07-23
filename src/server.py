#!/usr/bin/env/python3

import argparse
import logging
import os
import time

import flask
import flask_restful


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

_logger = logging.getLogger("server")
_logger.setLevel(logging.DEBUG)

class HelloWorld(flask_restful.Resource):
    def get(self):
        return "Hello world!"

class OuAlive(flask_restful.Resource):
    def post(self, ou_id):
        _logger.info("%s is alive!", ou_id)
        return None

class OuDataFile(flask_restful.Resource):
    def get(self, ou_id, filepath):
        print(flask.request)
        print(flask.request.data)

    def put(self, ou_id, filepath):
        logger = flask.current_app.logger
        data_dir = flask.current_app.config["OU_DATA_DIR"]
        data = flask.request.data
        offset = int(flask.request.args["offset"])

        localpath = flask.safe_join(data_dir, ou_id, "data", filepath)
        os.makedirs(os.path.dirname(localpath), exist_ok=True)

        with open(localpath, "a+b") as f:
            # Note: seeking past the end of the file and then writing will fill the gap with zeros
            f.seek(offset)
            f.write(data)
            logger.info("%s wrote %d bytes at offset %d", localpath, len(data), offset)

# Main
#=================================================================

if __name__ == "__main__":
    app = flask.Flask(__name__)
    app.config['OU_DATA_DIR'] = "remote_data"

    api = flask_restful.Api(app)
    api.add_resource(HelloWorld, "/")
    api.add_resource(OuAlive, "/ou/<string:ou_id>/alive")
    api.add_resource(OuDataFile, "/ou/<string:ou_id>/data/<path:filepath>")

    app.run(host='0.0.0.0', port=8080, debug=True)
