# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# BEWARE don't put anything in this file except exceptions
from werkzeug.exceptions import NotFound


class SiteNotSpecifiedError(Exception):
	def __init__(self, *args, **kwargs):
		self.message = "Please specify --site sitename"
		super(Exception, self).__init__(self.message)


class ValidationError(Exception):
	http_status_code = 417


class AuthenticationError(Exception):
	http_status_code = 401


class SessionExpired(Exception):
	http_status_code = 401


class PermissionError(Exception):
	http_status_code = 403


class DoesNotExistError(ValidationError):
	http_status_code = 404


class PageDoesNotExistError(ValidationError):
	http_status_code = 404


class NameError(Exception):
	http_status_code = 409


class OutgoingEmailError(Exception):
	http_status_code = 501


class SessionStopped(Exception):
	http_status_code = 503


class UnsupportedMediaType(Exception):
	http_status_code = 415


class RequestToken(Exception):
	http_status_code = 200


class Redirect(Exception):
	http_status_code = 301


class CSRFTokenError(Exception):
	http_status_code = 400


class TooManyRequestsError(Exception):
	http_status_code = 429


class ImproperDBConfigurationError(Exception):
	"""
	Used when frappe detects that database or tables are not properly
	configured
	"""

	def __init__(self, reason, msg=None):
		if not msg:
			msg = "MariaDb is not properly configured"
		super().__init__(msg)
		self.reason = reason


class DuplicateEntryError(NameError):
	pass


class DataError(ValidationError):
	pass


class UnknownDomainError(Exception):
	pass


class MappingMismatchError(ValidationError):
	pass


class InvalidStatusError(ValidationError):
	pass


class MandatoryError(ValidationError):
	pass


class NonNegativeError(ValidationError):
	pass


class InvalidSignatureError(ValidationError):
	pass


class RateLimitExceededError(ValidationError):
	pass


class CannotChangeConstantError(ValidationError):
	pass


class CharacterLengthExceededError(ValidationError):
	pass


class UpdateAfterSubmitError(ValidationError):
	pass


class LinkValidationError(ValidationError):
	pass


class CancelledLinkError(LinkValidationError):
	pass


class DocstatusTransitionError(ValidationError):
	pass


class TimestampMismatchError(ValidationError):
	pass


class EmptyTableError(ValidationError):
	pass


class LinkExistsError(ValidationError):
	pass


class InvalidEmailAddressError(ValidationError):
	pass


class InvalidNameError(ValidationError):
	pass


class InvalidPhoneNumberError(ValidationError):
	pass


class TemplateNotFoundError(ValidationError):
	pass


class UniqueValidationError(ValidationError):
	pass


class AppNotInstalledError(ValidationError):
	pass


class IncorrectSitePath(NotFound):
	pass


class ImplicitCommitError(ValidationError):
	pass


class RetryBackgroundJobError(Exception):
	pass


class DocumentLockedError(ValidationError):
	pass


class CircularLinkingError(ValidationError):
	pass


class SecurityException(Exception):
	pass


class InvalidColumnName(ValidationError):
	pass


class IncompatibleApp(ValidationError):
	pass


class InvalidDates(ValidationError):
	pass


class DataTooLongException(ValidationError):
	pass


class FileAlreadyAttachedException(Exception):
	pass


class DocumentAlreadyRestored(ValidationError):
	pass


class AttachmentLimitReached(ValidationError):
	pass


class QueryTimeoutError(Exception):
	pass


class QueryDeadlockError(Exception):
	pass


class InReadOnlyMode(ValidationError):
	http_status_code = 503  # temporarily not available


class SessionBootFailed(ValidationError):
	http_status_code = 500


class TooManyWritesError(Exception):
	pass


# OAuth exceptions
class InvalidAuthorizationHeader(CSRFTokenError):
	pass


class InvalidAuthorizationPrefix(CSRFTokenError):
	pass


class InvalidAuthorizationToken(CSRFTokenError):
	pass


class InvalidDatabaseFile(ValidationError):
	pass


class ExecutableNotFound(FileNotFoundError):
	pass


class InvalidRoundingMethod(FileNotFoundError):
	pass


class InvalidRemoteException(Exception):
	pass


class LinkExpired(ValidationError):
	http_status_code = 410
	title = "Link Expired"
	message = "The link has expired"


class InvalidKeyError(ValidationError):
	http_status_code = 401
	title = "Invalid Key"
	message = "The document key is invalid"
