import os
import socket

SERVER_HOST = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 21

BUFFER_SIZE = 4096
ENCODE_FORMAT = "utf-8"

DATA_DIRECTORY = os.path.join("..", "data")
RECEIVE_DIRECTORY = os.path.join("..", "download")

FILE_SIZE_UNITS = units = {
	"B": 1, "KB": 2 ** 10, "MB": 2 ** 20, "GB": 2 ** 30, "TB": 2 ** 40,
}
