#!/usr/bin/env/python3

import argparse
import http.server
import logging
import socketserver
import threading
import signal

# HTTP Request Handler
#=================================================================

class Co2UnitRequestHandler(http.server.BaseHTTPRequestHandler):

    def send_whole_response(self, code, content, content_type=None):

        if isinstance(content, str):
            content = content.encode("utf-8")
            if not content_type:
                content_type = "text/plain"
            if content_type.startswith("text/"):
                content_type += "; charset=utf-8"

        self.send_response(code)
        self.send_header('Content-type', content_type)
        self.send_header('Content-length',len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == "/":
            self.send_whole_response(200, "Hello, world!")
            return

        self.send_whole_response(404, "Unknown path: " + self.path)



# HTTP Server
#=================================================================

class ThreadingHttpServer(http.server.HTTPServer, socketserver.ThreadingMixIn):
    pass

def run_server(request_handler_class, server_class=ThreadingHttpServer, port=80, shutdown_grace_seconds=2):
    """
    Runs an HTTP server that shutsdown on SIGINT and SIGTERM

    This function handles all the fiddly bits for wiring up a server,
    threads, and signals properly:

    - server.shutdown() has to be called from a separate thread from
      server.serve_forever(), or else it deadlocks

    - Signal handlers execute in the main thread.

    - So if your signal handler is going to call server.shutdown(), then
      serve_forever() has to be started in a separate thread.

    - The server thread should have daemon = True so that you can quit with
      sys.exit() even if the thread doesn't stop.

    """

    server = server_class( ('', args.port), request_handler_class)

    def server_thread_main():
        logging.info("Starting server on port %d." , port)
        server.serve_forever()
        logging.info("Server has shut down cleanly.")

    server_thread = threading.Thread(target=server_thread_main)
    server_thread.daemon = True
    server_thread.start()

    def request_shutdown(signum=None, frame=None):
        if signum:
            logging.info("Got system signal %s.", signum)

        logging.info("Asking server to shut down...")
        server.shutdown()

        logging.info("Waiting for thread...")
        server_thread.join(shutdown_grace_seconds)

        if server_thread.isAlive():
            logging.error("Server thread is not stopping. Brute-force exiting with sys.exit().")
            sys.exit(1)

    # Install signal handlers
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    # Main thread has nothing to do but wait for signals
    while server_thread.isAlive():
        server_thread.join(1)

    logging.info("Server thread has shutdown cleanly")

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

# Main
#=================================================================

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)
    run_server(Co2UnitRequestHandler, port=args.port, shutdown_grace_seconds=args.shutdown_grace_seconds)
