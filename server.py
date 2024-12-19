import os
import json
import select
import socket
import struct
import time
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
		"""
		dict = {
			client_socket: {
				"host": client ip,
				"port": client port,
				"message": client message
				"sockets": [Sockets for download]
			}
		}
		"""

		self._inputs = [self._control_socket]
		self._outputs = []

		self._permitted_files = {}
		self._load_file_permissions()

	@property
	def address(self) -> tuple[str, int]:
		return self._host, self._port

	@staticmethod
	def _send(client_socket: socket.socket, data: str | bytes, retries: int = 5, delay: float = 0.1) -> int:
		"""
		Send data to the client socket

		:param client_socket: Socket to send
		:param data: Data to send, encode to bytes if necessary
		:return: Number of bytes sent
		"""
		if isinstance(data, str):
			data = data.encode(ENCODE_FORMAT)

		packed_data = struct.pack("!I", len(data)) + data

		total_sent = 0
		while total_sent < len(packed_data):
			try:
				current_sent = client_socket.send(packed_data[total_sent:])
				total_sent += current_sent
			except socket.error:
				if retries > 0:
					retries -= 1
					time.sleep(delay)
				else:
					break
		return total_sent

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
	def _get_open_port() -> Optional[int]:
		"""
		Get an open port from the operating system

		:return: Tuple of server IP and open port
		"""
		try:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
				sock.bind(("", 0))
				return sock.getsockname()[1]
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

			self._permitted_files.clear()
			for file_name in set(data.keys()):
				file_path = os.path.join(DATA_DIRECTORY, file_name)
				if os.path.exists(file_path):
					self._permitted_files[file_name] = os.path.getsize(file_path)
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
		return True, os.path.join(DATA_DIRECTORY, file_name)

	def _handle_chunk(self, client_socket: socket.socket, file_path: str) -> None:
		msg = self._recv(client_socket)
		split_msg = msg[1].split()
		if split_msg[0].upper() == "RETR":
			try:
				file_name = split_msg[1]
				try:
					offset = int(split_msg[2])
				except IndexError:
					offset = 0
				try:
					size = int(split_msg[3])
				except IndexError:
					size = self._permitted_files[file_name]
			except IndexError:  # Command missing parameter
				self._send(client_socket, "501 Syntax error: Expected file name after RETR command")
			else:
				self._retr(client_socket, file_path, offset, size)

		self._recv(client_socket)
		self._send(client_socket, "226 Goodbye!")
		client_socket.close()
		return None

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

	def _retr(self, client_socket: socket.socket, file_name: str, offset: int, size: int) -> None:
		"""
		Send requested file to client

		:param client_socket: Client socket
		:param file_name: File name
		:param offset: Starting byte offset
		:param size: Number of bytes to download
		:return: None
		"""
		file_status, file_path = self._get_file_status(client_socket, file_name)
		if not file_status:
			return None
		self._send(client_socket, "150 File status ok")
		# Send file data
		total_sent = 0
		with open(file_path, "rb") as file:
			file.seek(offset)
			# i = 0
			while True:
				data = file.read(min(BUFFER_SIZE, size - total_sent))
				if not data:
					break

				current_sent = self._send(client_socket, data) - 4
				total_sent += current_sent
				if total_sent >= size:
					break
				# print(f"Sent chunk {i} from offset {offset}: {len(data)} Bytes")
				# i += 1
			self._send(client_socket, "EOF")  # Mark the end of file, notify client to stop receiving
		print(f"Sent {total_sent} / {size} = {total_sent / size * 100} %")

		self._send(client_socket, "226 Transfer complete")
		return None

	def _accept_client(self) -> None:
		"""
		Accept incoming client connection, initialize client session

		:return: None
		"""
		client_socket, (client_host, client_port) = self._control_socket.accept()
		client_socket.setblocking(False)

		client_data = {
			"host": client_host,
			"port": client_port,
			"message": None
		}
		self._clients[client_socket] = client_data
		self._inputs.append(client_socket)
		print(f"Client connected: IP {client_host} on port {client_port}\n")
		return None

	def _remove_client(self, client_socket: socket.socket) -> None:
		"""
		Remove client record on server

		:param client_socket: Client socket
		:return: None
		"""
		print(f"Client disconnected. IP {self._clients[client_socket]['host']} on port {self._clients[client_socket]['port']}\n")

		self._clients.pop(client_socket)
		for record in (self._inputs, self._outputs):
			try:
				record.remove(client_socket)
			except ValueError:
				pass
		return None

	def _process_client_message(self, client_socket: socket.socket, message: str) -> bool:
		"""
		Process a message from client

		:param client_socket: Client socket
		:param message: Message received
		:return: Whether client still connecting
		"""
		split_msg = message.split()
		match split_msg[0].upper():
			case "LIST":
				self._list(client_socket)
			case "QUIT":
				self._quit(client_socket)
				self._remove_client(client_socket)
				return True
			case "RETR":
				try:
					file_name = split_msg[1]
					try:
						offset = int(split_msg[2])
					except IndexError:
						offset = 0
					try:
						size = int(split_msg[3])
					except IndexError:
						size = self._permitted_files[file_name]
				except IndexError:  # Command missing parameter
					self._send(client_socket, "501 Syntax error: Expected file name after RETR command")
				else:
					self._retr(client_socket, file_name, offset, size)
			case _:
				self._send(client_socket, f"501 Syntax error: Unknown command {message}")

		self._clients[client_socket]["message"] = None
		self._outputs.remove(client_socket)
		return True

	def run(self) -> None:
		self._control_socket.listen()
		self._control_socket.setblocking(False)
		print(f"Server listening: IP {self._host} on port {self._port}")

		while self._inputs:
			readable, writable, exceptional = select.select(self._inputs, self._outputs, self._inputs)

			for sock in readable:
				if sock is self._control_socket:
					self._accept_client()
				else:
					message = self._recv(sock)
					self._clients[sock]["message"] = message[1]
					self._outputs.append(sock)

			for sock in writable:
				if (message := self._clients[sock]["message"]) is not None:
					self._process_client_message(sock, message)

			for sock in exceptional:
				self._remove_client(sock)
		return None


if __name__ == "__main__":
	server = Server(host=SERVER_HOST, port=SERVER_PORT)
	server.run()
