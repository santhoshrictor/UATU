import urllib.request

for dev_id in (0, 1):
    url = f"http://127.0.0.1:8000/api/webcam-stream/{dev_id}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=3) as resp:
        content_type = resp.headers.get("Content-Type")
        print(f"Device {dev_id} stream ({url}): Content-Type = {content_type}")
        chunk = resp.read(1024)
        print(f"Device {dev_id} initial chunk received: {len(chunk)} bytes")

try:
    with urllib.request.urlopen("http://127.0.0.1:5173", timeout=2) as resp:
        print(f"Frontend on port 5173 is HTTP {resp.status}")
except Exception as e:
    print(f"Frontend on port 5173 check: {e}")
