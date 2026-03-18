import os
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pyngrok import ngrok


BASE_DIR = Path(__file__).resolve().parent
HOST = os.environ.get("BROWSER_APP_HOST", "0.0.0.0")
PORT = int(os.environ.get("BROWSER_APP_PORT", "8000"))
USE_NGROK = os.environ.get("USE_NGROK", "1").strip().lower() in {"1", "true", "yes", "on"}
NGROK_DOMAIN = os.environ.get("NGROK_DOMAIN", "").strip()


def build_handler():
    return partial(SimpleHTTPRequestHandler, directory=str(BASE_DIR))


def start_tunnel(port: int):
    auth_token = os.environ.get("NGROK_AUTHTOKEN", "").strip()
    if auth_token:
        ngrok.set_auth_token(auth_token)

    if NGROK_DOMAIN:
        return ngrok.connect(addr=str(port), proto="http", domain=NGROK_DOMAIN)

    return ngrok.connect(addr=str(port), proto="http")


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main():
    server = ThreadingHTTPServer((HOST, PORT), build_handler())
    tunnel = None

    try:
        if USE_NGROK:
            tunnel = start_tunnel(PORT)
            print(f"Public URL: {tunnel.public_url}")
            if NGROK_DOMAIN:
                print(f"Requested fixed domain: https://{NGROK_DOMAIN}")

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
        if tunnel is not None and tunnel.public_url:
            ngrok.disconnect(tunnel.public_url)
            ngrok.kill()


if __name__ == "__main__":
    main()