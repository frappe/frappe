# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


class DocStatus(int):
	def is_draft(self):
		return self == DocStatus.DRAFT

	def is_submitted(self):
		return self == DocStatus.SUMBITTED

	def is_cancelled(self):
		return self == DocStatus.CANCELLED

	# following methods have been kept for backwards compatibility

	@staticmethod
	def draft():
		return DocStatus.DRAFT

	@staticmethod
	def submitted():
		return DocStatus.SUMBITTED

	@staticmethod
	def cancelled():
		return DocStatus.CANCELLED


DocStatus.DRAFT = DocStatus(0)
DocStatus.SUMBITTED = DocStatus(1)
DocStatus.CANCELLED = DocStatus(2)
