# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import imaplib
import poplib
import chardet

from frappe.utils import cint


def get_port(doc):
	if not doc.incoming_port:
		if doc.use_imap:
			doc.incoming_port = imaplib.IMAP4_SSL_PORT if doc.use_ssl else imaplib.IMAP4_PORT

		else:
			doc.incoming_port = poplib.POP3_SSL_PORT if doc.use_ssl else poplib.POP3_PORT

	return cint(doc.incoming_port)


def decode_sequence(encoded_sequence) -> str:
	"""
	Decodes a encoded_sequence consisting of a tuple (string, charset_encoding). The function concatenates all chunks and returns the resulting decoded string.
	Args:
		encoded_sequence ((string, charset_encoding)): A list of tuples where each tuple contains a chunk of the string and its encoding.
	Returns:
		str: The decoded and concatenated sequence string.
	"""
	from frappe import safe_decode
	decoded_string = ""

	for chunk, encoding in encoded_sequence:
		if not isinstance(chunk, str):
			detected_encoding = encoding if encoding is not None and encoding != 'unknown-8bit' else chardet.detect(chunk)["encoding"]
			detected_encoding = detected_encoding if detected_encoding is not "ascii" else "unicode_escape"
			detected_encoding = detected_encoding if detected_encoding is not None else "UTF-8"

			decoded_string += chunk.decode(detected_encoding, 'replace')
		else:
			decoded_string += safe_decode(param=chunk)

	return decoded_string
