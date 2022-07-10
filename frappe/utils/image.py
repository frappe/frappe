# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import os

from PIL import Image


def resize_images(path, maxdim=700):
	size = (maxdim, maxdim)
	for basepath, folders, files in os.walk(path):
		for fname in files:
			extn = fname.rsplit(".", 1)[1]
			if extn in ("jpg", "jpeg", "png", "gif"):
				im = Image.open(os.path.join(basepath, fname))
				if im.size[0] > size[0] or im.size[1] > size[1]:
					im.thumbnail(size, Image.Resampling.LANCZOS)
					im.save(os.path.join(basepath, fname))

					print(f"resized {os.path.join(basepath, fname)}")


def strip_exif_data(content, content_type):
	"""Strips EXIF from image files which support it.

	Works by creating a new Image object which ignores exif by
	default and then extracts the binary data back into content.

	Returns:
	        Bytes: Stripped image content
	"""

	original_image = Image.open(io.BytesIO(content))
	output = io.BytesIO()
	# ref: https://stackoverflow.com/a/48248432
	if content_type == "image/jpeg" and original_image.mode in ("RGBA", "P"):
		original_image = original_image.convert("RGB")

	new_image = Image.new(original_image.mode, original_image.size)
	new_image.putdata(list(original_image.getdata()))
	new_image.save(output, format=content_type.split("/")[1])

	content = output.getvalue()

	return content


def optimize_image(
	content, content_type, max_width=1920, max_height=1080, optimize=True, quality=85
):
	if content_type == "image/svg+xml":
		return content

	image = Image.open(io.BytesIO(content))
	image_format = content_type.split("/")[1]
	size = max_width, max_height
	image.thumbnail(size, Image.Resampling.LANCZOS)

	output = io.BytesIO()
	image.save(
		output,
		format=image_format,
		optimize=optimize,
		quality=quality,
		save_all=True if image_format == "gif" else None,
	)

	optimized_content = output.getvalue()
	return optimized_content if len(optimized_content) < len(content) else content
