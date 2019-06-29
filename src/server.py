#!/usr/bin/env/python3

import argparse
import logging
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

_logger = logging.getLogger("server")
_logger.setLevel(logging.DEBUG)

class HelloWorld(flask_restful.Resource):
    def get(self):
        return "Hello world!"

class Alive(flask_restful.Resource):
    def post(self, ou_id):
        _logger.info("%s is alive!", ou_id)
        return None


# Main
#=================================================================

if __name__ == "__main__":
    app = flask.Flask(__name__)
    api = flask_restful.Api(app)
    api.add_resource(HelloWorld, "/")
    api.add_resource(Alive, "/ou/<string:ou_id>/alive")

    app.run(host='0.0.0.0', port=8080, debug=True)
