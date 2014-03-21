# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

# BEWARE don't put anything in this file except exceptions

class ValidationError(Exception):
	http_status_code = 417

class AuthenticationError(Exception):
	http_status_code = 401

class PermissionError(Exception):
	http_status_code = 403

class DoesNotExistError(ValidationError):
	http_status_code = 404

class DuplicateEntryError(Exception):
	http_status_code = 409
	
class OutgoingEmailError(Exception):
	http_status_code = 501
	
class SessionStopped(Exception):
	http_status_code = 503
	
class DataError(Exception): pass
class UnknownDomainError(Exception): pass
class MappingMismatchError(ValidationError): pass
class InvalidStatusError(ValidationError): pass
class MandatoryError(ValidationError): pass
class InvalidSignatureError(ValidationError): pass
class RateLimitExceededError(ValidationError): pass
class CannotChangeConstantError(ValidationError): pass
