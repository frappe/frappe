# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import os

def resize_images(path, maxdim=700):
	import Image
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
