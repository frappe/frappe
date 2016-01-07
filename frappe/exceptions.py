# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

# BEWARE don't put anything in this file except exceptions

from werkzeug.exceptions import NotFound
from MySQLdb import ProgrammingError as SQLError

class ValidationError(Exception):
	http_status_code = 417

class AuthenticationError(Exception):
	http_status_code = 401

class PermissionError(Exception):
	http_status_code = 403

class DoesNotExistError(ValidationError):
	http_status_code = 404

class NameError(Exception):
	http_status_code = 409

class OutgoingEmailError(Exception):
	http_status_code = 501

class SessionStopped(Exception):
	http_status_code = 503

class UnsupportedMediaType(Exception):
	http_status_code = 415

class Redirect(Exception):
	http_status_code = 301

class CSRFTokenError(Exception):
	http_status_code = 400

class DuplicateEntryError(NameError):pass
class DataError(ValidationError): pass
class UnknownDomainError(Exception): pass
class MappingMismatchError(ValidationError): pass
class InvalidStatusError(ValidationError): pass
class MandatoryError(ValidationError): pass
class InvalidSignatureError(ValidationError): pass
class RateLimitExceededError(ValidationError): pass
class CannotChangeConstantError(ValidationError): pass
class CharacterLengthExceededError(ValidationError): pass
class UpdateAfterSubmitError(ValidationError): pass
class LinkValidationError(ValidationError): pass
class CancelledLinkError(LinkValidationError): pass
class DocstatusTransitionError(ValidationError): pass
class TimestampMismatchError(ValidationError): pass
class EmptyTableError(ValidationError): pass
class LinkExistsError(ValidationError): pass
class InvalidEmailAddressError(ValidationError): pass
class TemplateNotFoundError(ValidationError): pass
class UniqueValidationError(ValidationError): pass
class AppNotInstalledError(ValidationError): pass
