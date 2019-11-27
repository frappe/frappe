from email.policy import EmailPolicy


class RFC5322Policy(EmailPolicy):
	def __init__(self, **kwargs):
		self._msg_id_headers = {'message-id', 'in-reply-to', 'references', 'resent-msg-id'}
		super().__init__(**kwargs)

	def _fold(self, name, value, refold_binary=False):
		if name.lower() in self._msg_id_headers and \
				self.max_line_length < 998 and \
				self.max_line_length - len(name) - 2 < len(value):
			# RFC 5322, section 2.1.1: "Each line of characters MUST be no
			# more than 998 characters, and SHOULD be no more than 78
			# characters, excluding the CRLF.". To avoid msg-id tokens from being folded
			# by means of RFC2047, fold identifier lines to the max length instead.
			return self.clone(max_line_length=998)._fold(name, value, refold_binary=refold_binary)
		return super()._fold(name, value, refold_binary=refold_binary)