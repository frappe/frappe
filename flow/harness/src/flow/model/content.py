"""Provider-neutral helpers for resolving durable user attachment references."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass

from flow.events import AttachmentContent, ToolResult, UserMessage

MISSING_ATTACHMENT_PLACEHOLDER = "(attachment unavailable: {name})"
# Neither chat-completions nor the Responses API accepts image parts inside a tool
# result, so tool images ride in a following user turn. This labels that turn so the
# model reads the images as tool output rather than as something the user just sent.
TOOL_IMAGE_PREFACE = "Images returned by the tool calls above:"


@dataclass(frozen=True)
class ResolvedImage:
	name: str
	mime_type: str
	data: bytes

	@property
	def data_url(self) -> str:
		encoded = base64.b64encode(self.data).decode("ascii")
		return f"data:{self.mime_type};base64,{encoded}"


def resolve_user_content(
	message: UserMessage,
	*,
	resolve_attachment: Callable[[str], bytes] | None,
) -> tuple[str, list[ResolvedImage]]:
	"""Return provider-ready text and images.

	Images are always resolved. Provider capability metadata is too unreliable to gate
	on — LiteLLM reports "no vision" for any model missing from its catalog, which
	silently replaced real images with a placeholder and left the model describing
	something it was never shown. A provider that cannot accept an image says so.
	"""
	text = message.text
	images: list[ResolvedImage] = []
	for attachment in message.attachments:
		data = _resolve(attachment, resolve_attachment)
		if data is None:
			text = _append(text, MISSING_ATTACHMENT_PLACEHOLDER.format(name=attachment.name))
			continue
		if attachment.kind == "text":
			try:
				body = data.decode("utf-8")
			except UnicodeDecodeError:
				text = _append(text, MISSING_ATTACHMENT_PLACEHOLDER.format(name=attachment.name))
				continue
			text = _append(text, f'<file name="{_xml_attr(attachment.name)}">\n{body}\n</file>')
		else:
			images.append(ResolvedImage(attachment.name, attachment.mime_type, data))
	return text, images


def resolve_tool_images(
	message: ToolResult,
	*,
	resolve_attachment: Callable[[str], bytes] | None,
) -> list[ResolvedImage]:
	"""Return the images a tool produced, skipping any whose bytes have gone missing.

	A missing image needs no placeholder: the tool's own result text already names what
	it read, so the model is told about the image either way.
	"""
	images: list[ResolvedImage] = []
	for attachment in message.attachments:
		data = _resolve(attachment, resolve_attachment)
		if data is not None:
			images.append(ResolvedImage(attachment.name, attachment.mime_type, data))
	return images


def attachment_summary(
	message: UserMessage,
	*,
	resolve_attachment: Callable[[str], bytes] | None = None,
	include_text_contents: bool = False,
) -> str:
	"""Textual representation used by token estimates and compaction."""
	text = message.text
	for attachment in message.attachments:
		if attachment.kind == "text" and include_text_contents:
			data = _resolve(attachment, resolve_attachment)
			try:
				body = data.decode("utf-8") if data is not None else None
			except UnicodeDecodeError:
				body = None
			if body is not None:
				text = _append(text, f'<file name="{_xml_attr(attachment.name)}">\n{body}\n</file>')
				continue
		text = _append(text, f"[Attached {attachment.kind}: {attachment.name}]")
	return text


def _resolve(
	attachment: AttachmentContent, resolve_attachment: Callable[[str], bytes] | None
) -> bytes | None:
	if resolve_attachment is None:
		return None
	try:
		return resolve_attachment(attachment.id)
	except (OSError, ValueError):
		return None


def _append(text: str, addition: str) -> str:
	return f"{text}\n{addition}" if text else addition


def _xml_attr(value: str) -> str:
	return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
