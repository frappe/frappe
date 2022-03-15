# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


class DocStatus(int):
	def is_draft(self):
		return self == self.draft()

	def is_submitted(self):
		return self == self.submitted()

	def is_cancelled(self):
		return self == self.cancelled()

	def is_locked(self):
		return self == self.locked()

	@classmethod
	def draft(cls):
		return cls(0)

	@classmethod
	def submitted(cls):
		return cls(1)

	@classmethod
	def cancelled(cls):
		return cls(2)

	@classmethod
	def locked(cls):
		return cls(3)
