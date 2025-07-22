# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import os

from PIL import Image

import frappe
from frappe import _


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


def strip_exif_data(content, content_type) -> bytes:
	"""Strip EXIF from image files which support it.

	Works by creating a new Image object which ignores exif by
	default and then extracts the binary data back into content.

	Return Stripped image content.
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


def optimize_image(content, content_type, max_width=1024, max_height=768, optimize=True, quality=85):
	if content_type == "image/svg+xml":
		return content

	try:
		image = Image.open(io.BytesIO(content))
		exif = image.getexif()
		width, height = image.size
		max_height = max(min(max_height, height * 0.8), 200)
		max_width = max(min(max_width, width * 0.8), 200)
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
			exif=exif,
		)
		optimized_content = output.getvalue()
		return optimized_content if len(optimized_content) < len(content) else content
	except Exception as e:
		frappe.msgprint(frappe._("Failed to optimize image: {0}").format(str(e)))
		return content


def sanitize_data_uri_svg(data_uri: str) -> str:
	"""Sanitize SVG in data URI and return sanitized data URI

	Args:
		data_uri: Data URI containing SVG content

	Returns:
		Sanitized data URI
	"""
	import base64

	from py_svg_hush import filter_svg

	# Extract SVG bytes
	if "base64," in data_uri:
		svg_bytes = base64.b64decode(data_uri.split("base64,")[1])
		is_base64 = True
	else:
		svg_bytes = data_uri.split(",")[1].encode("utf-8")
		is_base64 = False

	# Sanitize
	sanitized_bytes = filter_svg(svg_bytes)

	# Return sanitized data URI
	if is_base64:
		return f"data:image/svg+xml;base64,{base64.b64encode(sanitized_bytes).decode('utf-8')}"
	else:
		return f"data:image/svg+xml,{sanitized_bytes.decode('utf-8')}"


def sanitize_file_svg(file_path: str):
	"""Sanitize SVG file on disk

	Args:
		file_path: Path to SVG file relative to public folder
	"""
	from py_svg_hush import filter_svg

	full_path = frappe.get_site_path("public", file_path.lstrip("/"))
	if os.path.exists(full_path):
		with open(full_path, "rb") as f:
			svg_bytes = f.read()

		sanitized_bytes = filter_svg(svg_bytes)

		with open(full_path, "wb") as f:
			f.write(sanitized_bytes)
