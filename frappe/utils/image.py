# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import os

from PIL import Image


def resize_images(path, maxdim=700):
	"""
	Resize all the images in the specified path that have file extensions of jpg,
	jpeg, png, or gif.

	Args:
	    path (str): The path to the directory containing the images.
	    maxdim (int, optional): The maximum dimension of the resized images. Defaults to 700.
	"""
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
	"""
	Strips EXIF from image files which support it.

	Works by creating a new Image object which ignores exif by
	default and then extracts the binary data back into content.

	Args:
	    content (bytes): The image content.
	    content_type (str): The content type of the image.

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
	content, content_type, max_width=1024, max_height=768, optimize=True, quality=85
):
	"""
 Optimize the given image content.

	    This function resizes the image to the specified maximum width and
 height, optimizes it, and returns the optimized image content if it is
 smaller in size than the original content.

	    If the content type is 'image/svg+xml', the function returns the content
 as it is without any modifications.

 Args:
  content: The image content.
  content_type: The content type of the image.
  max_width (optional): The maximum width of the image after resizing. Defaults to 1024.
  max_height (optional): The maximum height of the image after resizing. Defaults to 768.
  optimize (optional): Whether to optimize the image. Defaults to True.
  quality (optional): The quality of the optimized image. Defaults to 85.

 Returns:
	            The optimized image content if it is smaller in size than the
  original content, otherwise the original content.
 """
	if content_type == "image/svg+xml":
	    return content

	image = Image.open(io.BytesIO(content))
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
	)

	optimized_content = output.getvalue()
	return optimized_content if len(optimized_content) < len(content) else content
