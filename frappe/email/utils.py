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
	
	
# from https://pypi.org/project/imap-tools/
# Use to support other codings than utf-8 in the IMAP folder name
class ImapUtf7:
# ENCODING
# --------
	import binascii
	
	from typing import Iterable, MutableSequence
	
	@classmethod
	def _modified_base64(cls, value: str) -> bytes:
		return cls.binascii.b2a_base64(value.encode('utf-16be')).rstrip(b'\n=').replace(b'/', b',')


	@classmethod
	def _do_b64(cls, _in: Iterable[str], r: MutableSequence[bytes]):
		if _in:
			r.append(b'&' + cls._modified_base64(''.join(_in)) + b'-')
		del _in[:]

	@classmethod
	def encode(cls, value: str) -> bytes:
		res = []
		_in = []
		for char in value:
			ord_c = ord(char)
			if 0x20 <= ord_c <= 0x25 or 0x27 <= ord_c <= 0x7e:
				cls._do_b64(_in, res)
				res.append(char.encode())
			elif char == '&':
				cls._do_b64(_in, res)
				res.append(b'&-')
			else:
				_in.append(char)
		cls._do_b64(_in, res)
		return b''.join(res)


# DECODING
# --------
	@classmethod
	def _modified_unbase64(cls, value: bytearray) -> str:
		return cls.binascii.a2b_base64(value.replace(b',', b'/') + b'===').decode('utf-16be')


	@classmethod
	def decode(cls, value: bytes) -> str:
		res = []
		decode_arr = bytearray()
		for char in value:
			if char == ord('&') and not decode_arr:
				decode_arr.append(ord('&'))
			elif char == ord('-') and decode_arr:
				if len(decode_arr) == 1:
					res.append('&')
				else:
					res.append(cls._modified_unbase64(decode_arr[1:]))
				decode_arr = bytearray()
			elif decode_arr:
				decode_arr.append(char)
			else:
				res.append(chr(char))
		if decode_arr:
			res.append(cls._modified_unbase64(decode_arr[1:]))
		return ''.join(res)
