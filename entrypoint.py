import os
import subprocess
import time
import urllib.request
import json
import re
import signal
import sys
from datetime import datetime

from notifier import notify_startup

# ================= Configuration =================
TUNNEL_TOKEN = os.environ.get("TUNNEL_TOKEN", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "")
PORT = os.environ.get("PORT", "10000")

def main():
    print("Starting AFS System Wrapper...")
    
    # 1. Start Gunicorn Web Server
    print(f"Starting Gunicorn on port {PORT}...")
    gunicorn_cmd = ["gunicorn", "-w", "1", "-b", f"0.0.0.0:{PORT}", "--timeout", "300", "app:app"]
    web_process = subprocess.Popen(gunicorn_cmd)
    
    # Wait for the web server to be ready
    time.sleep(3)
    
    if web_process.poll() is not None:
        print("Error: Gunicorn failed to start.")
        sys.exit(1)
        
    # 2. Start Cloudflare Tunnel
    cloudflared_cmd = []
    use_quick_tunnel = False
    
    if TUNNEL_TOKEN:
        print("Starting Cloudflare Named Tunnel...")
        cloudflared_cmd = ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", TUNNEL_TOKEN]
        if PUBLIC_URL:
            notify_startup(PUBLIC_URL)
        else:
            print("[Warning] TUNNEL_TOKEN provided but PUBLIC_URL is missing. Please set PUBLIC_URL in .env to get Discord notifications.")
    else:
        print("Starting Cloudflare Quick Tunnel...")
        cloudflared_cmd = ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PORT}"]
        use_quick_tunnel = True
        
    # cloudflared logs to stderr and stdout
    tunnel_process = subprocess.Popen(
        cloudflared_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    url_found = False
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    def cleanup(signum, frame):
        print("Shutting down services...")
        web_process.terminate()
        tunnel_process.terminate()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Monitor tunnel output
    try:
        while True:
            # Check if any process died
            if web_process.poll() is not None:
                print("Web process died.")
                break
            if tunnel_process.poll() is not None:
                print("Tunnel process died.")
                break
                
            # Read tunnel logs
            line = tunnel_process.stdout.readline()
            if line:
                print(f"[Cloudflared] {line.strip()}")
                
                # If quick tunnel and haven't found URL yet, search for it
                if use_quick_tunnel and not url_found:
                    match = url_pattern.search(line)
                    if match:
                        url = match.group(0)
                        print(f"[Wrapper] Discovered Quick Tunnel URL: {url}")
                        notify_startup(url)
                        url_found = True
            else:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        cleanup(None, None)
        
    finally:
        cleanup(None, None)

if __name__ == "__main__":
    main()
