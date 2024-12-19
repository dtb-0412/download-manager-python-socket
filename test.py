import os
import select
import socket
import struct
import threading
from typing import Optional

from constants import SERVER_HOST, SERVER_PORT, BUFFER_SIZE, DATA_DIRECTORY


class Server:
	def __init__(self,
				 host: str,
				 port: int):
		self._host = host
		self._port = port

		self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._socket.bind((host, port))
		self._socket.listen()

	@staticmethod
	def _send(client_socket: socket.socket, data: str) -> None:
		packed_data = struct.pack("!I", len(data)) + data.encode("utf-8")
		client_socket.sendall(packed_data)
		return None

	@staticmethod
	def _send_raw(client_socket: socket.socket, data: bytes) -> int:
		packed_data = struct.pack("!I", len(data)) + data
		return client_socket.send(packed_data)

	@staticmethod
	def _recv(client_socket: socket.socket) -> Optional[str]:
		header = Server._recv_all(client_socket, 4)
		if not header:
			return None

		size = struct.unpack("!I", header)[0]
		return Server._recv_all(client_socket, size).decode("utf-8")

	@staticmethod
	def _recv_all(client_socket: socket.socket, size: int) -> Optional[bytes]:
		data = bytearray()
		while (current_size := len(data)) < size:
			packet = client_socket.recv(size - current_size)
			if not packet:
				return None
			data.extend(packet)
		return data

	def _retr(self, client_socket: socket.socket, file_name: str) -> None:
		# Transfer file data
		file_path = os.path.join(DATA_DIRECTORY, file_name)
		print("Begin")
		i = 0
		with open(file_path, "rb") as file:
			print("Opened file")
			while True:
				data = file.read(BUFFER_SIZE)
				# print(f"Read\n{data.decode('utf-8')}")
				print(f"Read chunk {i}")
				if not data:
					print("EOF")
					break

				size = self._send_raw(client_socket, data)
				# ack = self._recv(client_socket)
				# print(ack)
				print(f"Sent: {size} bytes | Chunk: {i}\n")
				i += 1
		print("End")
		self._send(client_socket, "EOF")
		return None

	def _handle_client(self, client_socket: socket.socket) -> None:
		try:
			while True:
				split_message = self._recv(client_socket).split()
				match split_message[0].upper():
					case "GET" | "RETR":
						self._retr(client_socket, split_message[1])
					case "QUIT":
						client_socket.close()
						break
		except Exception as e:
			print(f"Exception encountered: {e}")
		return None

	def run(self) -> None:
		client_socket, client_address = self._socket.accept()
		# client_socket.setblocking(False)
		self._handle_client(client_socket)
		client_socket.close()
		# while True:
		# 	client_socket, client_address = self._socket.accept()
		# 	thread = threading.Thread(target=self._handle_client, args=[client_socket])
		# 	thread.start()


if __name__ == "__main__":
	server = Server(host=SERVER_HOST, port=SERVER_PORT)
	server.run()
