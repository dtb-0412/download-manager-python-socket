import socket
from pathlib import Path

IP = socket.gethostbyname(socket.gethostname())
PORT = 8080
ADDR = (IP, PORT)
FORMAT = "utf-8"
BUFFER_SIZE = 262144  # 256 KiB (256 * 1024)
FILE_PATH = "data\\sample_video_35mb.mp4"


def download(sock: socket.socket, file_path: str) -> bool:
	sock.send(f"RETR {file_path}".encode(FORMAT))
	msg = sock.recv(1024).decode(FORMAT)
	print(msg)

	if msg.split()[0] != "150":
		print(msg)
		return False

	with open(f"data\\recv_{Path(file_path).name}", "wb") as file:
		while True:
			data = sock.recv(BUFFER_SIZE)
			# Important: data == b"EOF" misses a lot due to some reasons (buffering, network delay, ...) which causes "EOF" to not come alone
			# in a separate chunk. Catching it using endswith() is crucial
			if data.endswith("EOF".encode(FORMAT)):
				break
			file.write(data)

	sock.send("Received".encode(FORMAT))
	msg = sock.recv(1024).decode(FORMAT)
	print(msg)
	return True



def disconnect(sock: socket.socket) -> None:
	sock.send("QUIT".encode(FORMAT))
	sock.recv(1024).decode(FORMAT)
	sock.close()
	return None


def main():
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect((IP, PORT))
	sock.recv(1024).decode(FORMAT)

	download(sock, FILE_PATH)
	disconnect(sock)
	return None


if __name__ == "__main__":
	main()
	