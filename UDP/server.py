import socket
import json
import os

SERVER_IP = "127.0.0.1"
SERVER_PORT = 8888
BUFFER_SIZE = 4096  # Kích thước buffer để nhận dữ liệu

def handle_client(sock):
    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            request = data.decode().strip()

            try:
                filename, chunk_info = request.split(" ", 1)
                chunk_id, offset_start, offset_end = map(int, chunk_info[1:-1].split(","))

                with open("filelist.json", "r") as f:
                    filelist = json.load(f)

                if filename not in filelist:
                    sock.sendto(b"File not found\n", addr)
                    continue

                filepath = os.path.join("files", filename)
                filesize = filelist[filename]

                if offset_end > filesize:
                    offset_end = filesize

                with open(filepath, "rb") as f:
                    f.seek(offset_start)
                    chunk_data = f.read(offset_end - offset_start)

                response = f"{chunk_id},{len(chunk_data)}|{chunk_data.decode(errors='ignore')}" # Gửi kèm chunk_id và kích thước chunk
                sock.sendto(response.encode(), addr)


            except (ValueError, IndexError):
                sock.sendto(b"Invalid request\n", addr)

        except ConnectionResetError:
            print(f"Client {addr} disconnected.")
            break  # Thoát khỏi vòng lặp khi client ngắt kết nối


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_IP, SERVER_PORT))
    print(f"Server started on {SERVER_IP}:{SERVER_PORT}")

    while True:
        handle_client(sock)


if __name__ == "__main__":
    main()