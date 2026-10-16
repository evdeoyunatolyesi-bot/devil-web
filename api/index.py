from http.server import BaseHTTPRequestHandler
import json, hashlib, hmac, os, time, threading
from urllib.parse import urlparse, parse_qs

ROOM_SECRET = os.environ.get("ROOM_SECRET", "change-this-secret-before-deploying")
ROOMS = {}
LOCK = threading.Lock()
MAX_MESSAGES = 100
ONLINE_SECONDS = 18

def room_key(password):
    return hmac.new(ROOM_SECRET.encode(), password.encode(), hashlib.sha256).hexdigest()

def json_bytes(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")

def get_room(key):
    return ROOMS.setdefault(key, {"members": {}, "messages": []})

def clean_online(room, now):
    for member in room["members"].values():
        member["online"] = (now - member.get("last_seen", 0)) <= ONLINE_SECONDS

class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.endswith("/api") or parsed.path == "/api/":
            return self._send(200, {"ok": True, "name": "DEVIL CHATS", "message": "API is running"})
        if parsed.path.endswith("/messages") or parsed.path.endswith("/status"):
            query = parse_qs(parsed.query)
            password = query.get("password", [""])[0]
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                return self._send(400, {"ok": False, "error": "Passphrase must be 8–128 characters."})
            key = room_key(password)
            now = int(time.time())
            with LOCK:
                room = get_room(key)
                clean_online(room, now)
                if parsed.path.endswith("/messages"):
                    result = {"ok": True, "messages": room["messages"][-MAX_MESSAGES:]}
                else:
                    members = sorted(room["members"].values(), key=lambda m: m.get("joined_at", 0))
                    result = {
                        "ok": True,
                        "online_count": sum(1 for m in members if m.get("online")),
                        "joined_count": len(members),
                        "members": [
                            {"username": m["username"], "joined_at": m["joined_at"],
                             "last_seen": m["last_seen"], "online": bool(m.get("online"))}
                            for m in members
                        ]
                    }
            return self._send(200, result)
        return self._send(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 12000:
                return self._send(413, {"ok": False, "error": "Request too large."})
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"ok": False, "error": "Invalid JSON."})

        if parsed.path.endswith("/join"):
            username = str(data.get("username", "")).strip()[:24]
            password = data.get("password", "")
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                return self._send(400, {"ok": False, "error": "Passphrase must be 8–128 characters."})
            if not (2 <= len(username) <= 24) or not all(ch.isalnum() or ch in "_-" for ch in username):
                return self._send(400, {"ok": False, "error": "Username must be 2–24 letters, numbers, _ or -."})
            key = room_key(password)
            now = int(time.time())
            with LOCK:
                room = get_room(key)
                clean_online(room, now)
                online_members = [m for m in room["members"].values() if m.get("online")]
                if any(m["username"].lower() == username.lower() for m in online_members):
                    return self._send(409, {"ok": False, "error": "That username is already online in this room."})
                if len(online_members) >= 2:
                    return self._send(409, {"ok": False, "error": "This room already has two online users."})
                token = hashlib.sha256(f"{username}:{time.time_ns()}".encode()).hexdigest()
                room["members"][token] = {"username": username, "joined_at": now, "last_seen": now, "online": True}
                waiting = len(online_members) == 0
                members = list(room["members"].values())
            return self._send(200, {"ok": True, "username": username, "token": token, "waiting": waiting})

        if parsed.path.endswith("/heartbeat") or parsed.path.endswith("/leave"):
            username = str(data.get("username", "")).strip()[:24]
            password = data.get("password", "")
            token = str(data.get("token", ""))
            if not isinstance(password, str) or not 8 <= len(password) <= 128 or not token:
                return self._send(400, {"ok": False, "error": "Missing room session."})
            key = room_key(password)
            now = int(time.time())
            with LOCK:
                room = get_room(key)
                member = room["members"].get(token)
                if member:
                    if parsed.path.endswith("/leave"):
                        member["online"] = False
                        member["last_seen"] = now
                    else:
                        member["last_seen"] = now
                        member["online"] = True
            return self._send(200, {"ok": True})

        if parsed.path.endswith("/send"):
            username = str(data.get("username", "Guest"))[:24]
            password = data.get("password", "")
            message = str(data.get("message", "")).strip()
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                return self._send(400, {"ok": False, "error": "Passphrase must be 8–128 characters."})
            if not message or len(message) > 2000:
                return self._send(400, {"ok": False, "error": "Message must be 1–2000 characters."})
            key = room_key(password)
            item = {"username": username, "message": message, "time": int(time.time())}
            with LOCK:
                room = get_room(key)
                room["messages"].append(item)
                room["messages"] = room["messages"][-MAX_MESSAGES:]
            return self._send(200, {"ok": True, "message": item})

        return self._send(404, {"ok": False, "error": "Unknown endpoint."})

    def log_message(self, format, *args):
        return
