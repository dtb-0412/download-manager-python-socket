import os
import select
import socket
import struct
from typing import Optional

from constants import SERVER_HOST, SERVER_PORT, ENCODE_FORMAT, RECEIVE_DIRECTORY


class Client:
	def __init__(self):
		self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	@staticmethod
	def _connect(client_socket: socket.socket, address: tuple[str, int]) -> bool:
		try:
			client_socket.connect(address)
		except TimeoutError:
			print("Connection timed out")
			return False
		return True

	@staticmethod
	def _send(client_socket: socket.socket, data: str) -> None:
		packed_data = struct.pack("!I", len(data)) + data.encode(ENCODE_FORMAT)
		client_socket.sendall(packed_data)
		return None

	@staticmethod
	def _recv(client_socket: socket.socket) -> Optional[str]:
		header = Client._recv_all(client_socket, 4)
		if not header:
			return None

		size = struct.unpack("!I", header)[0]
		return Client._recv_all(client_socket, size).decode(ENCODE_FORMAT)

	@staticmethod
	def _recv_raw(client_socket: socket.socket) -> Optional[bytes]:
		header = Client._recv_all(client_socket, 4)
		if not header:
			return None

		size = struct.unpack("!I", header)[0]
		print(f"Size: {size} bytes")
		return Client._recv_all(client_socket, size)

	@staticmethod
	def _recv_all(client_socket: socket.socket, size: int) -> Optional[bytes]:
		data = bytearray()
		while (current_size := len(data)) < size:
			packet = client_socket.recv(size - current_size)
			if not packet:
				return None
			data.extend(packet)
		return data

	def _download(self, file_name: str, to_directory: str = RECEIVE_DIRECTORY, rename: Optional[str] = None) -> bool:
		self._send(self._control_socket, f"RETR {file_name}")

		file_path = os.path.join(to_directory, rename if rename is not None else file_name)

		print("Begin receive")
		with open(file_path, "wb") as file:
			print("Opened file")
			i = 0
			while True:
				data = self._recv_raw(self._control_socket)
				print(f"Received chunk {i}\n")

				if data == "EOF".encode(ENCODE_FORMAT):
					break
				file.write(data)
				print(f"Written chunk {i}\n")
				# self._send(self._control_socket, "ACK")
				i += 1
		print("End receive")
		return True

	def _disconnect(self, client_socket: socket.socket) -> None:
		self._send(client_socket, "QUIT")
		client_socket.close()
		return None

	def run(self, host: str, port: int) -> None:
		if not self._connect(self._control_socket, (host, port)):
			return None

		# self._control_socket.setblocking(False)
		file_name = "sample_video_141MB.mp4"  # "sample_video_87MB.mp4"
		if self._download(file_name, rename=f"recv_{file_name}"):
			print("Download completed")
		else:
			print("Download failed")
		self._disconnect(self._control_socket)
		return None


if __name__ == '__main__':
	client = Client()
	client.run(SERVER_HOST, SERVER_PORT)
