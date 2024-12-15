import socket
import os
import threading
import json

SERVER_IP = "127.0.0.1"
SERVER_PORT = 8888
BUFFER_SIZE = 4096
NUM_CHUNKS = 5  # Số lượng chunk để download đồng thời

def download_chunk(sock, filename, chunk_id, offset_start, offset_end, output_filename):
    request = f"{filename} ({chunk_id},{offset_start},{offset_end})"
    sock.sendto(request.encode(), (SERVER_IP, SERVER_PORT))

    while True:
        try:
            response, _ = sock.recvfrom(BUFFER_SIZE * 16) # Tăng buffer size cho client
            response = response.decode()

            received_chunk_id_str, data = response.split("|", 1)
            received_chunk_id, chunk_size_str = map(str, received_chunk_id_str.split(","))


            if int(received_chunk_id) != chunk_id:
                print(f"Received wrong chunk ID: {received_chunk_id}, expected: {chunk_id}")
                continue # Bỏ qua nếu nhận sai chunk ID


            chunk_data = data.encode(errors='ignore') # Encode lại chunk data


            with open(output_filename, "r+b") as f:
                f.seek(offset_start)
                f.write(chunk_data)
            print(f"Chunk {chunk_id} downloaded successfully.")
            break

        except socket.timeout:
            print(f"Timeout for chunk {chunk_id}, retrying...")
            sock.sendto(request.encode(), (SERVER_IP, SERVER_PORT))


def download_file(filename, output_filename):
    with open("filelist.json", "r") as f:
        filelist = json.load(f)

    if filename not in filelist:
        print("File not found")
        return

    filesize = filelist[filename]
    chunk_size = filesize // NUM_CHUNKS

    # Tạo file output với kích thước bằng file gốc
    with open(output_filename, "wb") as f:
        f.seek(filesize - 1)
        f.write(b"\0")


    threads = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5) # Set timeout cho socket
        for i in range(NUM_CHUNKS):
            offset_start = i * chunk_size
            offset_end = (i + 1) * chunk_size
            if i == NUM_CHUNKS - 1:
                offset_end = filesize  # Đảm bảo chunk cuối cùng bao gồm toàn bộ dữ liệu còn lại

            thread = threading.Thread(target=download_chunk, args=(sock, filename, i, offset_start, offset_end, output_filename))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    print(f"File {filename} downloaded successfully as {output_filename}")


def main():
    filename = input("Enter filename to download: ")
    output_filename = input("Enter output filename: ")
    download_file(filename, output_filename)

if __name__ == "__main__":
    main()