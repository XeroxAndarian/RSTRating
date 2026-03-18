import os
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
HOST = os.environ.get("BROWSER_APP_HOST", "0.0.0.0")
PORT = int(os.environ.get("BROWSER_APP_PORT", "8000"))


def build_handler():
    return partial(SimpleHTTPRequestHandler, directory=str(BASE_DIR))


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main():
    server = ThreadingHTTPServer((HOST, PORT), build_handler())

    try:
        print(f"Local URL: http://127.0.0.1:{PORT}")
        if HOST == "0.0.0.0":
            print(f"LAN URL: http://{get_lan_ip()}:{PORT}")
        else:
            print(f"Bound URL: http://{HOST}:{PORT}")
        print("Serving BrowserApp/index.html")
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()