import abc
from typing import TYPE_CHECKING, Optional

import frappe
from frappe import _

if TYPE_CHECKING:
	from frappe.communications.doctype.communication.communication import Communication
	from frappe.communications.doctype.notification.notification import Notification
	from frappe.model.document import Document


class OutgoingCommunicationHandler(metaclass=abc.ABCMeta):
	@classmethod
	def __subclasshook__(cls, subclass):
		return (
			hasattr(subclass, "_validate_communication")
			and callable(subclass._validate_communication)
			and hasattr(subclass, "_send_implementation")
			and callable(subclass._send_implementation)
			and hasattr(subclass, "_communication_medium")
			and not callable(subclass._communication_medium)
			or NotImplemented
		)

	@classmethod
	def send(
		cls,
		comm: Communication,
		name: str | None = None,
		log: bool = True,
		ignore_permissions: bool = False,
	):
		"""
		Send the communication through the medium and log into Comunication log if desired

		:param comm: The unsaved communication document of the communication DocType
		:param name: The name of the controller, if None, it's either a singleton DocType
		             and uses the only possible controller or its a bridging doctype that
		             implements delayed sending (such as an email or notification queue)
		:param log:  save the communcation after sending
		:param ignore_permissions: whether to ignore if the user has permission to send
		             communication for this particular medium on this particular document

		:raises frappe.throw: throws on misconiguration or, optionally, sending errors
		"""
		if (
			not ignore_permissions
			and not frappe.has_permission(
				doctype=comm.reference_doctype,
				ptype=cls._communication_medium.lower(),
				doc=comm.reference_docname,
			)
		):
			raise frappe.PermissionError(
				f"You are not allowed to send communication via {cls._communication_medium} related to: {comm.reference_doctype} {comm.reference_docname}"
			)

		comm.communication_medium = cls._communication_medium

		if name:
			controller = frappe.get_doc(cls.DOCTYPE, name)
		elif frappe.model.is_single(cls.DOCTYPE):
			controller = frappe.get_single(cls.DOCTYPE)
		else:
			# briding doctype, such as a queue
			# controller, which is also an instance of that doctype, may or may not be saved
			controller = frappe.get_doc(cls.DOCTYPE)

		controller._validate_communitation(comm)

		successful = controller._send_implementation(comm)

		msg = ""

		if successful:
			msg += _("Successfully sent to following recipients: {0}").format(
				"\n\t" + "\n\t".join(successful)
			)

		unsuccessful = set(comm.recipients) - set(successful)

		if unsuccessful:
			msg += _("\nFailed to send to following recipients: {0}").format(
				"\n\t" + "\n\t".join(unsuccessful)
			)

		if log:
			comm.recipients = "\n".join(comm.recipients)
			comm.save()

		# TODO: mute in async scenarios - how to?
		if True:
			frappe.msgprint(msg)

	@abc.abstractmethod
	def _validate_communication(self, comm: Communication):
		"""
		Validate the communcation according to the requirement of the medium

		Note: is expected to mutate the in-memory Communication object in case it supplements or corrects values.

		:raises frappe.throw: throws on errors
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def _send_implementation(self, comm: Communication):
		"""
		Send the communication through the medium

		Note: is expected to mutate the in-memory Communication object, at least, to set the correct medium.

		:returns list: returns a tuple of lists of successful recipients
		:raises frappe.throw: throws on misconiguration or, optionally, sending errors
		"""
		raise NotImplementedError


class NotificationHandler(metaclass=abc.ABCMeta):
	@classmethod
	def __subclasshook__(cls, subclass):
		return (
			hasattr(subclass, "_get_notification_recipients")
			and callable(subclass._get_notification_recipients)
			and hasattr(subclass, "_get_notification_sender")
			and callable(subclass._get_notification_sender)
			and hasattr(subclass, "_log_notification")
			and callable(subclass._log_notification)
			or NotImplemented
		)

	@abc.abstractmethod
	def _get_notification_recipients(
		self, notification: Notification, doc: Document, context: dict
	) -> list[str]:
		"""
		Renders the recipient list for a notification and a particular medium.

		:param notification: Notification doctype
		:param doc: Document for which the Notification is rendered
		:param context: Notification context used for rendering; here: for evaluating a potential recipient condition

		:returns: list of strings representing the recipients for a particular medium
		:raises frappe.throw: throws on error
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def _get_notification_sender(
		self, notification: Notification, doc: Document, context: dict
	) -> str:
		"""
		Renders the sendr  for a notification and a particular medium.

		:param notification: Notification doctype
		:param doc: Document for which the Notification is rendered
		:param context: Notification context used for rendering; here: for evaluating a potential recipient condition

		:returns: string representing the sender
		:raises frappe.throw: throws on error
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def _log_notification(self, notification: Notification, doc: Document, context: dict) -> bool:
		"""
		Returns whether to log notification for this medium into the communication log.

		:param notification: Notification doctype
		:param doc: Document for which the Notification is rendered
		:param context: Notification context used for rendering; here: for evaluating a potential recipient condition

		:returns bool: True -> Yes / False -> No
		"""
		raise NotImplementedError
