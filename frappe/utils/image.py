# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import print_function, unicode_literals

import os


def resize_images(path, maxdim=700):
	from PIL import Image

	size = (maxdim, maxdim)
	for basepath, folders, files in os.walk(path):
		for fname in files:
			extn = fname.rsplit(".", 1)[1]
			if extn in ("jpg", "jpeg", "png", "gif"):
				im = Image.open(os.path.join(basepath, fname))
				if im.size[0] > size[0] or im.size[1] > size[1]:
					im.thumbnail(size, Image.ANTIALIAS)
					im.save(os.path.join(basepath, fname))

					print("resized {0}".format(os.path.join(basepath, fname)))


def strip_exif_data(content, content_type):
	"""Strips EXIF from image files which support it.

	Works by creating a new Image object which ignores exif by
	default and then extracts the binary data back into content.

	Returns:
	        Bytes: Stripped image content
	"""

	import io

	from PIL import Image

	original_image = Image.open(io.BytesIO(content))
	output = io.BytesIO()

	new_image = Image.new(original_image.mode, original_image.size)
	new_image.putdata(list(original_image.getdata()))
	new_image.save(output, format=content_type.split("/")[1])

	content = output.getvalue()

	return content
