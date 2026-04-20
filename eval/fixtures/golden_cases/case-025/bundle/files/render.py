"""Vulnerable template renderer -- user input directly in HTML."""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        name = query.get("name", ["Guest"])[0]
        html = f"<html><body><h1>Hello, {name}!</h1></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())
