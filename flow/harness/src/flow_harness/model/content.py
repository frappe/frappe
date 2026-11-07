"""Provider-neutral helpers for resolving durable user attachment references."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass

from flow_harness.events import AttachmentContent, ToolResult, UserMessage

NON_VISION_IMAGE_PLACEHOLDER = "(image contents unavailable to the current model)"
MISSING_ATTACHMENT_PLACEHOLDER = "(attachment unavailable: {name})"
FILE_PLACEHOLDER = "(contents not included; open it with your tools at {path})"


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
	supports_images: bool | None = None,
) -> tuple[str, list[ResolvedImage]]:
	"""Return provider-ready text and images. Only a model known not to accept images
	gets a placeholder; unknown capability sends the image and lets the provider decide."""
	text = message.text
	images: list[ResolvedImage] = []
	for attachment in message.attachments:
		if attachment.kind == "file":
			text = _append(text, _file_note(attachment))
			continue
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
		elif supports_images is False:
			text = _append(text, f"[Attached image: {attachment.name}]\n{NON_VISION_IMAGE_PLACEHOLDER}")
		else:
			images.append(ResolvedImage(attachment.name, attachment.mime_type, data))
	return text, images


def resolve_tool_images(
	message: ToolResult,
	*,
	resolve_attachment: Callable[[str], bytes] | None,
	supports_images: bool | None = None,
) -> list[ResolvedImage]:
	"""The images a tool produced; none for a model known not to accept images, and one
	whose bytes went missing is skipped, since the result text already names it."""
	images: list[ResolvedImage] = []
	if supports_images is False:
		return images
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
		if attachment.kind == "file":
			text = _append(text, _file_note(attachment))  # keeps the path through compaction
			continue
		text = _append(text, f"[Attached {attachment.kind}: {attachment.name}]")
	return text


def _file_note(attachment: AttachmentContent) -> str:
	size = attachment.size / 1024
	size_text = f"{size / 1024:.1f} MB" if size >= 1024 else f"{max(1, round(size))} KB"
	header = f"[Attached file: {attachment.name} ({attachment.mime_type}, {size_text})]"
	return f"{header}\n{FILE_PLACEHOLDER.format(path=attachment.path)}"


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
