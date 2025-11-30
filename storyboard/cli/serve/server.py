#!/usr/bin/env python3
"""HTTP server for viewing storyboard scenes."""

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class StoryboardRequestHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler for storyboard viewer."""

    def log_message(self, format: str, *args):
        """Suppress default logging to keep console clean."""
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path: str = parsed.path
        query: dict = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_viewer_html()
        elif path.startswith("/scene/"):
            self._serve_viewer_html()
        elif path == "/api/metadata":
            self._serve_root_metadata()
        elif path.startswith("/api/scene/"):
            self._serve_scene_metadata(path)
        elif path.startswith("/api/asset"):
            self._serve_asset(query)
        elif path.startswith("/static/"):
            self._serve_static_file(path)
        else:
            self._send_404()

    def _serve_viewer_html(self):
        """Serve the main viewer HTML page."""
        static_dir: Path = Path(__file__).parent / "static"
        html_path: Path = static_dir / "viewer.html"

        if not html_path.exists():
            self._send_error_response(500, "viewer.html not found")
            return

        with open(html_path, "rb") as f:
            content: bytes = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_static_file(self, path: str):
        """Serve static files (CSS/JS)."""
        filename: str = path.split("/static/", 1)[1]
        static_dir: Path = Path(__file__).parent / "static"
        file_path: Path = static_dir / filename

        if not file_path.exists():
            self._send_404()
            return

        # Security check
        try:
            if not file_path.resolve().is_relative_to(static_dir.resolve()):
                self._send_error_response(403, "Access denied")
                return
        except ValueError:
            self._send_error_response(403, "Access denied")
            return

        mime_type: str = self._get_mime_type(file_path)

        with open(file_path, "rb") as f:
            content: bytes = f.read()

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_root_metadata(self):
        """Serve root metadata.json."""
        try:
            scene_folder: Path = self.server.scene_folder
            metadata_path: Path = scene_folder / "metadata.json"

            if not metadata_path.exists():
                self._send_error_response(404, "metadata.json not found")
                return

            with open(metadata_path) as f:
                data: dict = json.load(f)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            self._send_error_response(500, str(e))

    def _serve_scene_metadata(self, path: str):
        """Serve scene-specific metadata.json."""
        try:
            scene_id: str = path.split("/api/scene/", 1)[1].rstrip("/")
            scene_folder: Path = self.server.scene_folder
            scene_metadata_path: Path = scene_folder / scene_id / "metadata.json"

            if not scene_metadata_path.exists():
                self._send_error_response(404, f"Scene not found: {scene_id}")
                return

            with open(scene_metadata_path) as f:
                data: dict = json.load(f)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            self._send_error_response(500, str(e))

    def _serve_asset(self, query: dict):
        """Serve asset files (images/audio)."""
        try:
            path_param = query.get("path", [None])[0]
            if not path_param:
                self._send_error_response(400, "Missing 'path' parameter")
                return

            scene_folder: Path = self.server.scene_folder
            asset_path: Path = self._resolve_asset_path(scene_folder, path_param)

            if not asset_path.exists():
                self._send_error_response(404, f"Asset not found: {path_param}")
                return

            # Security: Ensure path is within scene folder bounds
            try:
                if not asset_path.resolve().is_relative_to(
                    scene_folder.resolve().parent
                ):
                    self._send_error_response(403, "Access denied")
                    return
            except ValueError:
                self._send_error_response(403, "Access denied")
                return

            mime_type: str = self._get_mime_type(asset_path)

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(asset_path.stat().st_size))
            self.end_headers()

            with open(asset_path, "rb") as f:
                self.wfile.write(f.read())

        except Exception as e:
            self._send_error_response(500, str(e))

    def _resolve_asset_path(self, scene_folder: Path, relative_path: str) -> Path:
        """
        Resolve asset path from metadata relative path.

        Asset paths in metadata.json are relative to project root,
        typically starting with "output/". The scene_folder already
        points to the output directory, so we strip "output/" prefix.
        """
        if relative_path.startswith("output/"):
            relative_path = relative_path[len("output/") :]

        return scene_folder / relative_path

    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for file."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or "application/octet-stream"

    def _send_error_response(self, code: int, message: str):
        """Send JSON error response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def _send_404(self):
        """Send 404 Not Found response."""
        self._send_error_response(404, "Not found")


def start_server(scene_folder: Path, port: int):
    """Start the HTTP server."""
    server = HTTPServer(("localhost", port), StoryboardRequestHandler)
    server.scene_folder = scene_folder

    server.serve_forever()
