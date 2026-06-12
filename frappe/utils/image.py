# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import os
import threading

from PIL import Image, ImageOps, ExifTags

import frappe


# NOTE: Even though LANCZOS or BICUBIC family of filters are really good for faithful resizing Ops (particularly for interpolating) choosing this filter
# using Pillow results in much higher allocations (a simple thumbnail taking upto 15 Mb!) due to multiple allocations due to combination of chosen Layout by PIL and RGBA like mode.
# # For now NEAREST filter is suggested (to bypass higher latency(an much higher memory usage)!)

class PreAllocatedRawIO(io.RawIOBase):
	"""Subclass to allow Pre-allocating a buffer to reduce `grow` calls during re-allocations!
	   Even though for recent Python Versions `io.DEFAULT_BUFFER_SIZE` is pretty Big, but not enough for most of larger images!
	   For PIL specific operations, as PIL expects such Class implements `file.read`, `file.seek` and `file.tell` methods only!
	NOTE: Interface could be more flexible but we have to make work with PIL which expects it to work like IO.BytesIO like!
	"""
	def __init__(self, size:int):
		self._buffer = bytearray(size) # backing  buffer.
		self._pos = 0
		self._size = size

	def readable(self): return True
	def writable(self): return True
	def seekable(self): return True

	def read(self, size:int = -1) -> bytes:
		"""
		NOTE: by-default aka without some (pre) seeking  (after some write) to a valid position,it will always return NONE (aka no bytes/data).
		"""
		start = self._pos
		end =  self._pos
		if size >= 0:
			end = min(self._size , self._pos + size)
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
		# NOTE: we just return upto the `self._pos` for this.(aka would be conditioned on.seek !)
		return bytes(memoryview(self._buffer)[:self._pos])

	def getbuffer(self):
		return self._buffer

def _resize_images_thread_func(image_abs_paths:list[os.PathLike | str], maxdim:int):
	# Thread target function to resize images.
	for abs_path in image_abs_paths:
		im = Image.open(abs_path)
		size = (maxdim, maxdim)
		if im.size[0] > size[0] or im.size[1] > size[1]:
			im.thumbnail(size, Image.Resampling.NEAREST)
			# Overwrite, according to existing logic, not even a warning !
			_, image_format = os.path.splitext(abs_path)
			image_format = image_format.strip(".").lower()
			im.save(
				abs_path,
				format = image_format,
				compress_level = 1 if image_format=="png" else 6
			)

def resize_images(path:os.PathLike, maxdim=700, max_workers:int = 3):
	"""
	max_workers:int , No of threads to use to speed up resizing a batch of image.
		Though it would depend on concurrent load, but can have linear gains for example using 3 workers for a batch as low as 20 images (HD size)!!
		We keep it a 3, for now due to non-predicatability of work-load due to weird mixing of multiple different services !
		It results in almost 3 times speed up for almost all cases.
	"""
	# size = (maxdim, maxdim)
	image_abs_paths = list()
	for basepath, folders, files in os.walk(path, topdown = True):  # noqa: B007
		for fname in files:
			extn = fname.rsplit(".", 1)[1]
			if extn in ("jpg", "jpeg", "png", "gif"):
				image_abs_paths.append(os.path.join(basepath, fname))

	# Create threads on demand and divide work.
	n_workers = max_workers
	threads_arr:list[threading.Thread] = list()
	remainder = len(image_abs_paths) % n_workers
	avg = len(image_abs_paths) // n_workers
	for i in range(n_workers):
		start,end = i*avg, (i+1)*avg
		if i == n_workers - 1:
			end += remainder
		work = image_abs_paths[start:end]

		t = threading.Thread(target = _resize_images_thread_func , args = (work, maxdim))
		t.start()
		threads_arr.append(t)
		del t
	del avg, remainder

	# wait for them to finish.
	for t in threads_arr:
		t.join()


def strip_exif_data(content:bytes, content_type:str) -> bytes:
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

	# Save.
	# TODO: just update the `content` underlying buffer to remove exif data,rather than creating  a new copy!
	if content_type == "image/jpeg" and original_image.mode in ("RGBA", "P"):
		# ref: https://stackoverflow.com/a/48248432,
		# Costly OP but required, due to choice of layout by PILLOW i think!
		original_image = original_image.convert("RGB")

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
			image.thumbnail(size, Image.Resampling.NEAREST)

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
