"""Fixed template renderer -- user input escaped before rendering."""

import html as html_mod
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        name = html_mod.escape(query.get("name", ["Guest"])[0])
        body = f"<html><body><h1>Hello, {name}!</h1></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())
