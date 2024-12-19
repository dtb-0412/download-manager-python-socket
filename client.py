import os
import json
# import re
import socket
import struct
from typing import Optional

from constants import SERVER_HOST, SERVER_PORT, ENCODE_FORMAT, RECEIVE_DIRECTORY  # , FILE_SIZE_UNITS


class Client:
	def __init__(self):
		self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		self._permitted_files = {}

	@staticmethod
	def _connect(client_socket: socket.socket, address: tuple[str, int]) -> bool:
		"""
		Connect client socket to the given address

		:param client_socket: Socket need connecting
		:param address: Address to connect to
		:return: Whether connection succeeded
		"""
		try:
			client_socket.connect(address)
		except TimeoutError:
			print("Connection timed out")
			return False
		return True

	@staticmethod
	def _send(client_socket: socket.socket, data: str | bytes) -> None:
		"""
		Send data to the client socket

		:param client_socket: Socket to send
		:param data: Data to send, encode to bytes if necessary
		:return: None
		"""
		if isinstance(data, str):
			data = data.encode(ENCODE_FORMAT)

		packed_data = struct.pack("!I", len(data)) + data
		client_socket.sendall(packed_data)
		return None

	@staticmethod
	def _recv(client_socket: socket.socket) -> tuple[int, str]:
		size, raw_data = Client._recv_raw(client_socket)
		return size, raw_data.decode(ENCODE_FORMAT)

	@staticmethod
	def _recv_raw(client_socket: socket.socket) -> tuple[int, bytes]:
		"""
		Receive data from client socket

		:param client_socket: Socket to receive
		:return: Tuple of data received and its size
		"""
		header = Client._recv_n(client_socket, 4)
		if not header:
			return 0, bytes("")

		size = struct.unpack("!I", header)[0]
		data = Client._recv_n(client_socket, size)
		return size, data

	@staticmethod
	def _recv_n(client_socket: socket.socket, size: int) -> Optional[bytes]:
		"""
		Receive exactly size bytes from client socket

		:param client_socket: Socket to receive
		:param size: Number of bytes to receive
		:return: Data received
		"""
		data = bytearray()
		while (current_size := len(data)) < size:
			packet = client_socket.recv(size - current_size)
			if not packet:
				return None
			data.extend(packet)
		return data

	# @staticmethod
	# def _parse_file_size(file_size: str) -> int:
	# 	"""
	# 	Parse file size string into number of bytes
	#
	# 	:param file_size: File size string
	# 	:return: Number of bytes
	# 	"""
	# 	file_size = file_size.upper()
	# 	if not re.match(r" ", file_size):
	# 		file_size = re.sub(r"([KMGT]|KI|MI|GI|TI)", r" \1", file_size)
	#
	# 	number, unit = [string.strip() for string in file_size.split()]
	# 	if FILE_SIZE_UNITS.get(unit) is None:
	# 		return 0
	# 	return int(float(number) * FILE_SIZE_UNITS[unit])

	def _get_permitted_files(self) -> None:
		"""
		Get list of permitted files from server

		:return: None
		"""
		self._send(self._socket, "LIST")
		msg = self._recv(self._socket)
		if not msg[1].startswith("150"):
			return None

		msg = self._recv(self._socket)
		self._permitted_files = json.loads(msg[1])
		# data = json.loads(msg[1])
		# self._permitted_files = {key: self._parse_file_size(value) for key, value in data.items()}

		self._recv(self._socket)

		# Print to console
		print("Permitted files:")
		for file_name, file_size in self._permitted_files.items():
			print(f"{file_name}: {file_size} Bytes")
		print("--------------------------------------------------")
		return None

	def _download(self, file_name: str, file_size: int, to_directory: str = RECEIVE_DIRECTORY, rename: Optional[str] = None) -> bool:
		"""
		Download file from server

		:param file_name: File name on server
		:param file_size: File size in bytes
		:param to_directory: Download directory
		:param rename: Rename downloaded file to this, default to original file name
		:return: Whether download succeeded
		"""
		self._send(self._socket, f"RETR {file_name}")  # Request file from server
		msg = self._recv(self._socket)
		if not msg[1].startswith("150"):  # File unavailable
			return False
		# Receive file data to buffer
		i = 0
		bytes_received = 0
		file_buffer = bytearray()
		while True:
			size, data = self._recv_raw(self._socket)
			if data == "EOF".encode(ENCODE_FORMAT):
				print("Finished\n")
				break
			file_buffer.extend(data)

			bytes_received += size
			progress = bytes_received / file_size * 100
			print(f"Downloaded chunk {i}: {bytes_received} (+{size}) / {file_size} Bytes, {progress} %")
			i += 1
		# Handle duplicate file name
		name, extension = os.path.splitext(file_name if rename is None else rename)

		file_index = 1
		file_path = os.path.join(to_directory, f"{name}{extension}",)
		while os.path.exists(file_path):  # File already exists, create a new numbered name
			file_path = os.path.join(to_directory, f"{name} ({file_index}){extension}")
			file_index += 1
		# Write data to file
		with open(file_path, "wb") as file:
			file.write(file_buffer)

		self._recv(self._socket)
		return True

	def _disconnect(self, client_socket: socket.socket) -> None:
		"""
		Disconnect from server

		:param client_socket: Client socket
		:return: None
		"""
		self._send(client_socket, "QUIT")  # Send QUIT to notify server that client is disconnecting
		self._recv(client_socket)
		client_socket.close()
		return None

	def run(self, host: str, port: int) -> None:
		if not self._connect(self._socket, (host, port)):
			print(f"Couldn't connect to server: IP {host} on port {port}")
			return None

		self._get_permitted_files()

		for file_name, file_size in self._permitted_files.items():
			if self._download(file_name, file_size, rename=f"RECV_{file_name}"):
				print(f"Download completed: {file_name}")
			else:
				print(f"Download failed: {file_name}")

		self._disconnect(self._socket)
		return None


if __name__ == '__main__':
	client = Client()
	client.run(SERVER_HOST, SERVER_PORT)
