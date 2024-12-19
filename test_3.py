import re

from constants import FILE_SIZE_UNITS

def _parse_file_size(file_size: str) -> int:
	"""
	Parse file size string into number of bytes

	:param file_size: File size string
	:return: Number of bytes
	"""
	file_size = file_size.upper()
	if not re.match(r" ", file_size):
		file_size = re.sub(r"([KMGT]|KI|MI|GI|TI)", r" \1", file_size)

	number, unit = [string.strip() for string in file_size.split()]
	if FILE_SIZE_UNITS.get(unit) is None:
		return 0
	return int(float(number) * FILE_SIZE_UNITS[unit])


size = "1MiB"
print(f"{_parse_file_size(size)} Bytes")
