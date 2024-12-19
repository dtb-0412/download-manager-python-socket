import os
import json
# import select
import socket
import struct
from typing import Optional

from constants import SERVER_HOST, SERVER_PORT, BUFFER_SIZE, ENCODE_FORMAT, DATA_DIRECTORY


class Server:
	def __init__(self,
				 host: str,
				 port: int):
		self._host = host
		self._port = port

		self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._control_socket.bind(self.address)

		self._clients = {}

		self._permitted_files = {}
		self._load_file_permissions()

	@property
	def address(self) -> tuple[str, int]:
		return self._host, self._port

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
	def _recv(client_socket: socket.socket) -> Optional[tuple[int, str]]:
		"""
		Receive data from client socket

		:param client_socket: Socket to receive
		:return: Tuple of data received and its size
		"""
		header = Server._recv_n(client_socket, 4)
		if not header:
			return None

		size = struct.unpack("!I", header)[0]
		data = Server._recv_n(client_socket, size).decode(ENCODE_FORMAT)
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

	@staticmethod
	def _get_open_address() -> Optional[tuple[str, int]]:
		"""
		Get an open port from the operating system

		:return: Tuple of server IP and open port
		"""
		try:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
				sock.bind(("", 0))
				return sock.getsockname()
		except OSError:
			print(f"Service unavailable, please reconnect later")
		return None

	def _load_file_permissions(self) -> None:
		"""
		Load file permissions

		:return: None
		"""
		with open("file_permission.json", "r") as file:
			data = json.load(file).get("permitted_files")
			if not data:
				return None

			self._permitted_files = {file_name: os.path.getsize(os.path.join(DATA_DIRECTORY, file_name)) for file_name in set(data.keys())}
		return None

	def _get_file_status(self, client_socket: socket.socket, file_name: str) -> tuple[bool, Optional[str]]:
		"""
		Get file status, send error message if file is unavailable

		:param client_socket: Client socket
		:param file_name: File name
		:return: Tuple of file status and file path on server
		"""
		# Check file permissions
		if self._permitted_files and self._permitted_files.get(file_name) is None:
			self._send(client_socket, f"550 File unavailable: {file_name}")
			return False, None
		# Check file existence
		file_path = os.path.join(DATA_DIRECTORY, file_name)
		if not os.path.exists(file_path):
			self._send(client_socket, f"550 File missing: {file_name}")
			return False, None
		return True, file_path

	def _list(self, client_socket: socket.socket) -> None:
		"""
		Send list of permitted files to client

		:param client_socket: Client socket
		:return:
		"""
		if not self._permitted_files:
			self._send(client_socket, f"550 File permissions unavailable")
			return None

		self._send(client_socket, "150 File status ok")
		self._send(client_socket, json.dumps(self._permitted_files))
		self._send(client_socket, "226 File permissions sent")
		return None

	def _quit(self, client_socket: socket.socket) -> None:
		"""
		Client disconnect, close sockets

		:param client_socket: Client socket
		:return: None
		"""
		self._send(client_socket, "221 Goodbye!")
		client_socket.close()
		return None

	def _retr(self, client_socket: socket.socket, file_name: str) -> None:
		"""
		Send requested file to client

		:param client_socket: Client socket
		:param file_name: File name
		:return: None
		"""
		# Check file status
		file_status, file_path = self._get_file_status(client_socket, file_name)
		if not file_status:
			return None
		self._send(client_socket, "150 File status ok")
		# Send file data
		with open(file_path, "rb") as file:
			i = 0
			while True:
				data = file.read(BUFFER_SIZE)
				if not data:
					break
				self._send(client_socket, data)
				print(f"Sent chunk {i}: {len(data)} Bytes")
				i += 1
			self._send(client_socket, "EOF")  # Mark the end of file, notify client to stop receiving

		self._send(client_socket, "226 Transfer complete")
		return None

	def _process_client_message(self, client_socket: socket.socket, message: str) -> bool:
		"""
		Process a message from client

		:param client_socket: Client socket
		:param message: Message received
		:return: Whether client still connecting
		"""
		split_message = message.split()
		match split_message[0].upper():
			case "LIST":
				self._list(client_socket)
			case "QUIT":
				self._quit(client_socket)
				return False
			case "RETR":
				try:
					file_name = split_message[1]
				except IndexError:  # Command missing parameter
					self._send(client_socket, "501 Syntax error: Expected file name after RETR command")
				else:
					self._retr(client_socket, file_name)
			case _:
				self._send(client_socket, f"501 Syntax error: Unknown command {message}")
		return True

	def _handle_client(self, client_socket: socket.socket, client_address: tuple[str, int]) -> None:
		"""
		Handle client socket

		:param client_socket: Client socket
		:param client_address: Client address
		:return: None
		"""
		while True:
			message = self._recv(client_socket)
			try:
				if not self._process_client_message(client_socket, message[1]):
					break
			except Exception as e:
				print(f"Exception: {e}")
				break

		print(f"Client disconnected. IP {client_address[0]} on port {client_address[1]}\n")
		return None

	def run(self) -> None:
		self._control_socket.listen()
		self._control_socket.setblocking(False)

		while True:
			client_socket, client_address = self._control_socket.accept()
			client_socket.setblocking(False)
			self._handle_client(client_socket, client_address)
			self._control_socket.close()


if __name__ == "__main__":
	server = Server(host=SERVER_HOST, port=SERVER_PORT)
	server.run()
