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
		self.encrypt_password = self.browser.options.get("password", None)
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
			return body

		body_height = body.pages[0].mediabox.top
		body_transform = header_height = footer_height = header_body_top = 0

		if footer:
			footer_height = footer.pages[0].mediabox.top
			body_transform = footer_height

		if header:
			header_height = header.pages[0].mediabox.top
			header_transform = body_height + footer_height
			header_body_top = header_height + body_height + footer_height

		if header and not self.is_header_dynamic:
			for h in header.pages:
				self._transform(h, header_body_top, header_transform)

		for p in body.pages:
			if header_body_top:
				self._transform(p, header_body_top, body_transform)
			if header:
				if self.is_header_dynamic:
					p.merge_page(
						self._transform(header.pages[p.page_number], header_body_top, header_transform)
					)
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

			if footer:
				if self.is_footer_dynamic:
					p.merge_page(footer.pages[p.page_number])
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

		if output:
			output.append_pages_from_reader(body)
			return output

		writer = PdfWriter()
		writer.append_pages_from_reader(body)
		if self.encrypt_password:
			writer.encrypt(self.encrypt_password)

		return self.get_file_data_from_writer(writer)

	def _transform(self, page, page_top, ty):
		from pypdf import PdfWriter, Transformation

		transform = Transformation().translate(ty=ty)
		page.mediabox.upper_right = (page.mediabox.right, page_top)
		page.add_transformation(transform)
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
