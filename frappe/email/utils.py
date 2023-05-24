# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import imaplib
import poplib

from frappe.utils import cint

import chardet


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
		decoded_chunk = ""
		if not isinstance(chunk, str):
			detected_encoding = encoding if encoding is not None and encoding != 'unknown-8bit' else chardet.detect(chunk)["encoding"]
			decoded_chunk = safe_decode(param=chunk, encoding=detected_encoding)
		else:
			decoded_chunk = safe_decode(param=chunk)
		if isinstance(decoded_chunk, str):
			decoded_string += decoded_chunk
	return decoded_string
