import os
import json
import socket
import struct
import threading
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
			return 0, "".encode(ENCODE_FORMAT)

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

	@staticmethod
	def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', print_end="\r"):
		"""
		Call in a loop to create terminal progress bar
		@params:
			iteration   - Required  : current iteration (Int)
			total       - Required  : total iterations (Int)
			prefix      - Optional  : prefix string (Str)
			suffix      - Optional  : suffix string (Str)
			decimals    - Optional  : positive number of decimals in percent complete (Int)
			length      - Optional  : character length of bar (Int)
			fill        - Optional  : bar fill character (Str)
			print_end    - Optional  : end character (e.g. "\r", "\r\n") (Str)
		"""
		percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
		filled_length = int(length * iteration // total)
		bar = fill * filled_length + '-' * (length - filled_length)
		print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
		# Print New Line on Complete
		if iteration == total:
			print()

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

	@staticmethod
	def display_progress(progress):
		print("\rDownload Progress: ", end="")
		for part in range(4):
			print(f"Part {part + 1}: {progress[part]:.2f}% | ", end="")
		print("", end="", flush=True)
		return None

	def _handle_chunk(self, client_socket: socket.socket, file_name: str, offset: int, chunk_size: int, chunk_order: int, file_data: list,
					  progresses: list) -> None:
		self._send(client_socket, f"RETR {file_name} {offset} {chunk_size}")  # Request file from server
		self._recv(client_socket)  # Guaranteed file available
		# Receive file data to buffer
		total_received = 0
		file_buffer = bytearray()
		# print(f"Begin download chunk {chunk_order}:")
		while True:
			current_received, data = self._recv_raw(client_socket)
			if data == "EOF".encode(ENCODE_FORMAT):
				# print("Finished\n")
				break
			file_buffer.extend(data)
			total_received += current_received
			progresses[chunk_order] = int(total_received / chunk_size * 100)
			self.display_progress(progresses)

		# print(f"Finish download chunk {chunk_order}: {total_received} / {chunk_size} Bytes, {total_received / chunk_size * 100} %")
		file_data[chunk_order] = file_buffer
		self._recv(client_socket)
		self._disconnect(client_socket)
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
		file_data = [bytearray()] * 4
		whole, quotient = divmod(file_size, 5)
		first_3_chunks, last_chunk = divmod(whole + quotient, 3)
		chunk_sizes = [whole + first_3_chunks] * 3 + [whole + last_chunk]

		threads = []
		progresses = [0] * 4
		for chunk_order, chunk_size in enumerate(chunk_sizes):
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.connect((SERVER_HOST, SERVER_PORT))

			offset = sum(chunk_sizes[:chunk_order])
			thread = threading.Thread(target=self._handle_chunk, args=(sock, file_name, offset, chunk_size, chunk_order, file_data, progresses))
			threads.append(thread)
			thread.start()

		for thread in threads:
			thread.join()
		# Handle duplicate file name
		name, extension = os.path.splitext(file_name if rename is None else rename)

		file_index = 1
		file_path = os.path.join(to_directory, f"{name}{extension}",)
		while os.path.exists(file_path):  # File already exists, create a new numbered name
			file_path = os.path.join(to_directory, f"{name} ({file_index}){extension}")
			file_index += 1
		# Write data to file
		with open(file_path, "wb") as file:
			data = "".encode(ENCODE_FORMAT).join(file_data)
			file.write(data)
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
