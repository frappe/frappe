class PDFTransformer:
	def __init__(self, browser):
		self.browser = browser
		self.body_pdf = browser.body_pdf
		self.is_print_designer = browser.is_print_designer
		self._set_header_pdf()
		self._set_footer_pdf()
		if not self.header_pdf and not self.footer_pdf:
			return
		self.no_of_pages = len(self.body_pdf.pages)
		# if not header / footer then return body pdf

	def _set_header_pdf(self):
		self.header_pdf = None
		if hasattr(self.browser, "header_pdf"):
			self.header_pdf = self.browser.header_pdf
			self.is_header_dynamic = self.browser.is_header_dynamic

	def _set_footer_pdf(self):
		self.footer_pdf = None
		if hasattr(self.browser, "footer_pdf"):
			self.footer_pdf = self.browser.footer_pdf
			self.is_footer_dynamic = self.browser.is_footer_dynamic

	def transform_pdf(self, output=None):
		from pypdf import PdfWriter

		header = self.header_pdf
		body = self.body_pdf
		footer = self.footer_pdf

		if not header and not footer:
			if output:
				from io import BytesIO

				from pypdf import PdfReader

				reader = PdfReader(BytesIO(body))
				first_new_page = len(output.pages)
				output.append_pages_from_reader(reader)
				self._resolve_internal_links(output, reader, first_new_page)
				return output
			return body

		body_height = body.pages[0].mediabox.top
		body_transform = header_height = footer_height = 0

		if footer:
			footer_height = footer.pages[0].mediabox.top
			body_transform = footer_height

		if header:
			header_height = header.pages[0].mediabox.top
			header_transform = body_height + footer_height

		# full page height: the body was rendered on a page shortened by the
		# header/footer heights, so every body page must be raised above the
		# footer and its mediabox restored to the full paper height
		page_top = header_height + body_height + footer_height

		# Pre-transform every header page exactly once. A dynamic header can have
		# fewer pages than the body (pagination rounding), so the merge below
		# clamps the index like the footer path — transforming inline there would
		# translate a clamped page multiple times.
		if header:
			for h in header.pages:
				self._transform(h, page_top, header_transform)

		for p in body.pages:
			self._transform(p, page_top, body_transform)

			if header:
				if self.is_header_dynamic:
					p.merge_page(header.pages[min(p.page_number, len(header.pages) - 1)])
				elif self.is_print_designer:
					if p.page_number == 0:
						p.merge_page(header.pages[0])
					elif p.page_number == self.no_of_pages - 1:
						p.merge_page(header.pages[3])
					elif p.page_number % 2 == 0:
						p.merge_page(header.pages[2])
					else:
						p.merge_page(header.pages[1])
				else:
					p.merge_page(header.pages[0])

			# Footer pages are not transformed — they sit at y=0 naturally.
			if footer:
				if self.is_footer_dynamic and len(footer.pages) > 1:
					p.merge_page(footer.pages[min(p.page_number, len(footer.pages) - 1)])
				elif self.is_print_designer:
					if p.page_number == 0:
						p.merge_page(footer.pages[0])
					elif p.page_number == self.no_of_pages - 1:
						p.merge_page(footer.pages[3])
					elif p.page_number % 2 == 0:
						p.merge_page(footer.pages[2])
					else:
						p.merge_page(footer.pages[1])
				else:
					p.merge_page(footer.pages[0])

		writer = output or PdfWriter()
		first_new_page = len(writer.pages)
		writer.append_pages_from_reader(body)
		for page in writer.pages[first_new_page:]:
			page.compress_content_streams()
		self._resolve_internal_links(writer, body, first_new_page, body_transform)

		return output or self.get_file_data_from_writer(writer)

	def _resolve_internal_links(self, writer, reader, first_new_page, ty=0):
		from pypdf.generic import ArrayObject, FloatObject, NameObject

		destinations = reader.named_destinations
		for page in writer.pages[first_new_page:]:
			for annotation in page.get("/Annots", []):
				annotation = annotation.get_object()
				name = annotation.get("/Dest")
				if not isinstance(name, str) or name not in destinations:
					continue
				destination = destinations[name]
				target = writer.pages[first_new_page + reader.get_destination_page_number(destination)]
				annotation[NameObject("/Dest")] = ArrayObject(
					[
						target.indirect_reference,
						destination.typ,
						destination.left,
						FloatObject(destination.top + ty),
						destination.zoom,
					]
				)

	def _transform(self, page, page_top, ty):
		from pypdf.generic import FloatObject

		page.mediabox.upper_right = (page.mediabox.right, page_top)
		content = page.get_contents()
		content.set_data(f"q 1 0 0 1 0 {FloatObject(ty)} cm\n".encode() + content.get_data() + b"\nQ")
		page.replace_contents(content)
		for annotation in page.get("/Annots", []):
			annotation = annotation.get_object()
			for key in ("/Rect", "/QuadPoints"):
				if key in annotation:
					points = annotation[key]
					points[1::2] = [FloatObject(y + ty) for y in points[1::2]]
		return page

	def get_file_data_from_writer(self, writer_obj):
		from io import BytesIO

		# https://docs.python.org/3/library/io.html
		stream = BytesIO()
		writer_obj.write(stream)

		# Change the stream position to start of the stream
		stream.seek(0)

		# Read up to size bytes from the object and return them
		return stream.read()
