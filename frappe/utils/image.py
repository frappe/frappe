# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from _typeshed import ReadableBuffer
import io
import os

from PIL import Image, ImageOps, ExifTags

import frappe

class PreAllocatedRawIO(io.RawIOBase):
	"""Subclass to allow Pre-allocating a buffer to reduce `grow` calls during re-allocations!
	   Even though for recent Python Versions `io.DEFAULT_BUFFER_SIZE` is pretty Big, but not enough for most of larger images!
	   For PIL specific operations, as PIL expects such Class implements `file.read`, `file.seek` and `file.tell` methods only!
	"""
	def __init__(self, size:int):
		self._buffer = bytearray(size) # backing  buffer.
		self._pos = 0
		self._readable_size:int = 0   # we track possible readable range using this variable
		self._size = size

	def readable(self): return True
	def writable(self): return True
	def seekable(self): return True

	def read(self, size:int = -1) -> bytes:
		assert self._readable_size >= self._pos
		start = self._pos
		end =  self._readable_size
		if size >= 0:
			end = min(self._pos + size, self._readable_size)
		data = bytes(memoryview(self._buffer)[start:end])
		self._pos += len(data)
		return data

	def write(self, data:bytes) -> int:
		# assert (self._pos + len(data)) < self._size, "Since this Class expects that user know maximum possibly memory requirements, we don't handle any `grow` like calls, TODO: "
		if (self._pos + len(data)) >= self._size:
			# Re-grow. (as current capacity wouldn't be enough)
			# Don't go on sharing it across threads without any locking across write specifically!
			temp_buffer = bytearray(self._size * 2)
			memoryview(temp_buffer)[:self._pos] = memoryview(self._buffer)[:self._pos]
			del self._buffer
			self._buffer = temp_buffer
			self._size = len(temp_buffer)
			del temp_buffer

		if self._pos  >= self._size:
			return 0
		chunk_size = len(data)
		self._buffer[self._pos: self._pos + chunk_size] = data
		self._pos += chunk_size
		self._readable_size = max(self._readable_size, self._pos)
		return chunk_size

	def readinto(self, b) -> int:
		raise NotImplementedError

	def seek(self, offset:int, whence = io.SEEK_SET) -> int:
		assert offset >= 0, "For now Offset is expected to be positive !"
		if whence == io.SEEK_SET:
			self._pos = max(0, min(offset, self._size))
		elif whence == io.SEEK_CUR:
			self._pos = max(0, min(self._pos + offset, self._size))
		elif whence == io.SEEK_END:
			self._pos = max(0, min(self._size + offset, self._size))
		return self._pos

	def tell(self) -> int:
		return self._pos

	def getvalue(self) -> bytes:
		return bytes(memoryview(self._buffer)[:self._pos])

	def get_underlying_buffer(self):
		return self._buffer

def resize_images(path, maxdim=700):
	size = (maxdim, maxdim)
	for basepath, folders, files in os.walk(path):  # noqa: B007
		for fname in files:
			extn = fname.rsplit(".", 1)[1]
			if extn in ("jpg", "jpeg", "png", "gif"):
				im = Image.open(os.path.join(basepath, fname))
				if im.size[0] > size[0] or im.size[1] > size[1]:
					im.thumbnail(size, Image.Resampling.LANCZOS)
					im.save(os.path.join(basepath, fname))

					print(f"resized {os.path.join(basepath, fname)}")


def strip_exif_data(content:bytes, content_type) -> bytes:
	"""Strip EXIF from image files which support it.

	Works by creating a new Image object which ignores exif by
	default and then extracts the binary data back into content.

	Return Stripped image content.
	"""

	original_image = Image.open(io.BytesIO(content))
	exif = original_image.getexif()
	if exif.get(ExifTags.Base.Orientation):
		# Apply EXIF orientation to pixels before stripping the tag.
		# Even if there is no orientation data i.e nothing to , without in-place, it will create a copy!! (See imageOps/exif_orientation.py)
		# `in_place` will remove the `orientation` data from the content, except from that all assumptions about content should remain true if user further after call to this routine.
		# Actual `transpose` could occur only on `image` matrix, so `content` would be immune from this operation!
		ImageOps.exif_transpose(original_image, in_place= True)
		if content_type == "image/jpeg" and original_image.mode in ("RGBA", "P"):
			# ref: https://stackoverflow.com/a/48248432,
			# Costly OP but required, due to choice of layout by PILLOW i think!
			original_image = original_image.convert("RGB")

		# Save.
		output_pre = PreAllocatedRawIO(size = len(content) * 2)
		format = content_type.split("/")[1].strip().lower()
		if format == "png":
			# Pass compress level for PNGs.  https://github.com/python-pillow/Pillow/issues/1211
			original_image.save(output_pre, format = content_type.split("/")[1], compress_level = 1, exif=b"")
		else:
			original_image.save(output_pre, format = content_type.split("/")[1], exif=b"")

		encoded_data =  output_pre.getvalue()
		del output_pre, original_image
		return encoded_data
	else:
		del original_image, exif
		return content

def optimize_image(content, content_type, max_width=1024, max_height=768, optimize=True, quality=85):
	if content_type == "image/svg+xml":
		return content

	try:
		image = Image.open(io.BytesIO(content))
		exif = image.getexif()
		width, height = image.size
		max_height = max(min(max_height, height * 0.8), 200)
		max_width = max(min(max_width, width * 0.8), 200)
		if (width * height) < (max_height * max_width): # proxy to comparing len(content) with len(optimizied_content).
			return content
		else:
			image_format = content_type.split("/")[1]
			size = max_width, max_height
			image.thumbnail(size, Image.Resampling.LANCZOS)

			output_pre = PreAllocatedRawIO(size = len(content) * 2)
			image.save(
				output_pre,
				format=image_format,
				compress_level = 1 if image_format == "png" else 6,     # PNG `compression` can go out of hands,  https://github.com/python-pillow/Pillow/issues/1211
				quality=quality,
				save_all=True if image_format == "gif" else None,
				exif=exif,
			)
			optimized_content = output_pre.getvalue()
			del output_pre
			return optimized_content
	except Exception as e:
		frappe.msgprint(frappe._("Failed to optimize image: {0}").format(str(e)))
		return content
