#!/usr/bin/env python3
"""Serve only this workbench directory on 127.0.0.1 (no repo-wide exposure).

Supports HTTP Range for HTML5 video seeking/playback.
"""
from __future__ import annotations

import argparse
import functools
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".mp4": "video/mp4",
        ".json": "application/json",
        ".html": "text/html; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
    }

    def end_headers(self):
        # Help browser media element; keep loopback-only exposure.
        if self.path.endswith(".mp4"):
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        if not os.path.exists(path) or not os.path.isfile(path):
            self.send_error(404, "File not found")
            return None

        ctype = self.guess_type(path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs.st_size
        range_header = self.headers.get("Range")
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not m:
                f.close()
                self.send_error(400, "Invalid Range")
                return None
            start_s, end_s = m.group(1), m.group(2)
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else size - 1
            if start >= size or end >= size or start > end:
                f.close()
                self.send_error(416, "Requested Range Not Satisfiable")
                self.send_header("Content-Range", f"bytes */{size}")
                return None
            length = end - start + 1
            f.seek(start)
            self.send_response(206)
            self.send_header("Content-type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            self._range_length = length
            return f

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        self._range_length = None
        return f

    def copyfile(self, source, outputfile):
        length = getattr(self, "_range_length", None)
        if length is None:
            return super().copyfile(source, outputfile)
        remaining = length
        bufsize = 64 * 1024
        while remaining > 0:
            chunk = source.read(min(bufsize, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    handler = functools.partial(Handler, directory=str(root))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {root} on http://{args.host}:{args.port}/")
    print("Bind is loopback-only. Use SSH/Cursor port forward for local browser.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
