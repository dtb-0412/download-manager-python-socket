import os
import socket

IP = socket.gethostbyname(socket.gethostname())
PORT = 8080
ADDR = (IP, PORT)
FORMAT = "utf-8"
BUFFER_SIZE = 262144  # 256 KiB (256 * 1024)


"""
125: Start transferring
150: File status ok, ready for transferring
213: File status
221: Closing connection (client quit)
226: Closing connection, requested file action successful (file transfer only)
230: User logged in, proceed (authentication)
250: Requested file action okay, completed (non file-transfer only)
501: Syntax error in parameters or arguments
550: File unavailable (not found/no access)
"""


def _check_file_exists(conn: socket.socket, msg: list[str]) -> bool:
	try:
		file_path = msg[1]
	except IndexError:  # Command error, missing parameter
		conn.send(f"501 Syntax error: Expected file path after {msg[0]} command".encode(FORMAT))
		return False

	if not os.path.exists(file_path):
		conn.send("550 File not found".encode(FORMAT))
		return False
	return True


def _list(conn: socket.socket, msg: list[str]) -> None:
	try:
		path = msg[1]
	except IndexError:  # Command error, missing parameter
		conn.send("501 Syntax error: Expected directory/file path after LIST command".encode(FORMAT))
		return None

	if not os.path.exists(path):  # Directory/file not found
		conn.send(f"550 Directory/file not found".encode(FORMAT))
		return None

	conn.send("150 File status ok".encode(FORMAT))
	if os.path.isdir(path):  # Send list of files names
		conn.send(f"{os.listdir(path)}".encode(FORMAT))
	else:  # Send file information
		print(f"{os.stat(path)}")
		conn.send(f"{os.stat(path)}".encode(FORMAT))
	conn.send("226 Directory/file information sent".encode(FORMAT))
	return None


def _retr(conn: socket.socket, msg: list[str]) -> None:
	if not _check_file_exists(conn, msg):
		return None
	conn.send("150 File status ok".encode(FORMAT))
	# Transfer file data
	with open(msg[1], "rb") as file:
		while True:
			data = file.read(BUFFER_SIZE)
			if not data:
				break
			conn.send(data)

	conn.send("EOF".encode(FORMAT))
	conn.recv(1024).decode(FORMAT)  # Important: sending "EOF" and "226" consecutively sometimes causes the messages to mess up the order
	conn.send("226 Transfer complete".encode(FORMAT))
	return None


def _quit(conn: socket.socket) -> None:
	conn.send("221 Goodbye!".encode(FORMAT))
	conn.close()
	return None


def _size(conn: socket.socket, msg: list[str]) -> None:
	if not _check_file_exists(conn, msg):
		return None
	conn.send(f"150 {os.path.getsize(msg[1])}".encode(FORMAT))
	return None


def main():
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.bind((IP, PORT))
	sock.listen()

	conn, addr = sock.accept()
	conn.send("220 Service ready for new user".encode(FORMAT))

	while True:
		msg = conn.recv(1024).decode().split()
		match msg[0]:
			case "LIST":
				_list(conn, msg)
			case "GET" | "RETR":
				_retr(conn, msg)
			case "QUIT":
				_quit(conn)
				break
			case "SIZE":
				_size(conn, msg)
			case _:
				conn.send(f"501 Unknown command {msg}".encode(FORMAT))

	sock.close()
	return None


if __name__ == "__main__":
	main()
