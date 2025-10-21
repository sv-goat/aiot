import socket
import json

# ---- Simple HTTP Server ----
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)

print("Listening on", addr)

def handle_request(conn):
    try:
        req = b""
        # Keep reading until headers are done
        while b"\r\n\r\n" not in req:
            chunk = conn.recv(512)
            if not chunk:
                break
            req += chunk

        header, _, rest = req.partition(b"\r\n\r\n")
        header_str = header.decode()
        content_length = 0

        for line in header_str.split("\r\n"):
            if "Content-Length:" in line:
                content_length = int(line.split(":")[1].strip())

        # Read remaining body bytes
        body = rest
        while len(body) < content_length:
            chunk = conn.recv(512)
            if not chunk:
                break
            body += chunk

        body_str = body.decode()

        # --- Parse JSON and execute ---
        if "POST /run" not in header_str:
            conn.send(b"HTTP/1.1 404 Not Found\r\n\r\n")
            return

        data = json.loads(body_str)
        func_name = data.get("function")
        func = FUNCTIONS.get(func_name)

        if func:
            result = func()
            response = json.dumps({"ok": True, "result": result})
        else:
            response = json.dumps({"ok": False, "error": "unknown function"})

        conn.send(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n")
        conn.send(response.encode())

    except Exception as e:
        err = json.dumps({"ok": False, "error": str(e)})
        conn.send(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + err.encode())
    finally:
        conn.close()

# ---- Main Loop ----
while True:
    conn, addr = s.accept()
    handle_request(conn)