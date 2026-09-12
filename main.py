import socket
import threading
from urllib.parse import urlsplit

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 3128


def relay(source, destination):
    try:
        while True:
            data = source.recv(64 * 1024)
            if not data:
                break
            destination.sendall(data)
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass


def handle_connect(client, host, port):
    try:
        # DNS + TCP connection happen on Windows
        upstream = socket.create_connection((host, port), timeout=15)

        client.sendall(
            b"HTTP/1.1 200 Connection Established\r\n"
            b"\r\n"
        )

        # Bidirectional byte forwarding
        t1 = threading.Thread(
            target=relay,
            args=(client, upstream),
            daemon=True
        )
        t2 = threading.Thread(
            target=relay,
            args=(upstream, client),
            daemon=True
        )

        t1.start()
        t2.start()

        t1.join()
        t2.join()

    except Exception as e:
        print(f"CONNECT {host}:{port} failed: {e}")

        try:
            client.sendall(
                b"HTTP/1.1 502 Bad Gateway\r\n"
                b"Content-Length: 0\r\n"
                b"\r\n"
            )
        except OSError:
            pass

    finally:
        try:
            upstream.close()
        except:
            pass


def handle_client(client, address):
    print(f"Connection from {address}")

    try:
        # Read the HTTP request headers
        request = b""

        while b"\r\n\r\n" not in request:
            chunk = client.recv(4096)

            if not chunk:
                return

            request += chunk

            if len(request) > 64 * 1024:
                return

        header_end = request.find(b"\r\n\r\n")
        header_bytes = request[:header_end + 4]

        headers = header_bytes.decode("iso-8859-1")
        lines = headers.split("\r\n")

        request_line = lines[0]
        method, target, version = request_line.split(" ", 2)

        print(f"{address} -> {method} {target}")

        # HTTPS
        if method.upper() == "CONNECT":
            host, port = target.rsplit(":", 1)
            handle_connect(client, host, int(port))
            return

        # Plain HTTP
        parsed = urlsplit(target)

        if not parsed.hostname:
            client.sendall(
                b"HTTP/1.1 400 Bad Request\r\n"
                b"Content-Length: 0\r\n"
                b"\r\n"
            )
            return

        host = parsed.hostname
        port = parsed.port or 80

        upstream = socket.create_connection(
            (host, port),
            timeout=15
        )

        # Rewrite proxy request into a normal HTTP request.
        path = parsed.path or "/"

        if parsed.query:
            path += "?" + parsed.query

        new_request = (
            f"{method} {path} {version}\r\n"
        ).encode("iso-8859-1")

        # Forward headers, removing Proxy-specific headers.
        for line in lines[1:]:
            if not line:
                continue

            name = line.split(":", 1)[0].lower()

            if name in ("proxy-connection", "proxy-authenticate"):
                continue

            new_request += (line + "\r\n").encode("iso-8859-1")

        new_request += b"\r\n"

        upstream.sendall(new_request)

        # Forward response back to Spring
        relay(upstream, client)

    except Exception as e:
        print(f"Request from {address} failed: {e}")

    finally:
        try:
            client.close()
        except:
            pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    # IMPORTANT:
    # Only listen on localhost.
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(100)

    print(f"Proxy listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        client, address = server.accept()

        threading.Thread(
            target=handle_client,
            args=(client, address),
            daemon=True
        ).start()


if __name__ == "__main__":
    main()
