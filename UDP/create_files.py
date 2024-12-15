import json
import os

files_dir = "files"  # Tên thư mục chứa các file
file_list = {}

for filename in os.listdir(files_dir):
    filepath = os.path.join(files_dir, filename)
    if os.path.isfile(filepath):
        filesize = os.path.getsize(filepath)
        file_list[filename] = filesize

with open("filelist.json", "w") as f:
    json.dump(file_list, f, indent=4)

print("filelist.json created successfully.")