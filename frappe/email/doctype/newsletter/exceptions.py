# Copyright (c) 2021, nts Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

from nts.exceptions import ValidationError


class NewsletterAlreadySentError(ValidationError):
	pass


class NoRecipientFoundError(ValidationError):
	pass


class NewsletterNotSavedError(ValidationError):
	pass
