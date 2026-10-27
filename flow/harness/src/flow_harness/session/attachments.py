"""Session-scoped attachment storage and bounded image processing.

Attachment bytes live beside the session log, never inside JSONL events. Durable user
messages carry only immutable attachment metadata; model adapters resolve the bytes at
request time through this store.
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
import re
import shutil
import uuid
import warnings
from collections.abc import Collection
from tempfile import mkstemp
from threading import Lock

from PIL import Image, UnidentifiedImageError

from flow_harness.events import AttachmentContent

MAX_ATTACHMENTS_PER_MESSAGE = 10
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_TEXT_BYTES = 256 * 1024
SNIFF_BYTES = 8192  # how far read looks for binary
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2_000
MAX_IMAGE_PIXELS = 40_000_000
_ATTACHMENT_ID_RE = re.compile(r"^[a-f0-9]{24}$")
_SUPPORTED_IMAGE_FORMATS = {
	"JPEG": "image/jpeg",
	"PNG": "image/png",
	"GIF": "image/gif",
	"WEBP": "image/webp",
	"BMP": "image/bmp",
}


class AttachmentError(ValueError):
	"""An attachment is missing, unsafe, or unsupported."""


class AttachmentStore:
	def __init__(self, path: str):
		self.path = path
		self._lock = Lock()
		os.makedirs(path, mode=0o700, exist_ok=True)
		os.chmod(path, 0o700)

	def add_bytes(
		self,
		name: str,
		data: bytes,
	) -> AttachmentContent:
		"""Validate and store one browser image upload."""
		if not data:
			raise AttachmentError("attachment is empty")
		if len(data) > MAX_SOURCE_BYTES:
			raise AttachmentError(f"attachment exceeds the {MAX_SOURCE_BYTES // 1024 // 1024} MB limit")
		name = _safe_name(name)
		processed = _process_image(data)
		if processed is None:
			raise AttachmentError(f"{name} is not a supported image")
		return self._store_image(name, processed)

	def add_file(self, name: str, data: bytes, *, tools: Collection[str], path: str) -> AttachmentContent:
		"""Inline a mentioned image or small text; else point the model's tools at `path`."""
		if not data:
			raise AttachmentError("attachment is empty")
		if len(data) > MAX_SOURCE_BYTES:
			raise AttachmentError(f"attachment exceeds the {MAX_SOURCE_BYTES // 1024 // 1024} MB limit")
		name = _safe_name(name, keep_dirs=True)
		inline = self._add_inline(name, data)
		if inline is not None:
			return inline
		return self.add_reference(name, data, len(data), path, tools=tools)

	def add_reference(
		self, name: str, head: bytes, size: int, path: str, *, tools: Collection[str]
	) -> AttachmentContent:
		"""Record a project file the model's tools open where it lies; `head` is its start."""
		name = _safe_name(name, keep_dirs=True)
		_check_tools(name, head, tools)
		content = AttachmentContent(
			id=uuid.uuid4().hex[:24], name=name, mime_type=_file_type(name), size=size, kind="file", path=path
		)
		with self._lock:
			_write_private(self._meta_path(content.id), content.model_dump_json().encode())
		return content

	def _add_inline(self, name: str, data: bytes) -> AttachmentContent | None:
		"""Store an image or small UTF-8 text for the model to see; None for anything else."""
		try:
			processed_image = _process_image(data)
		except AttachmentError:
			return None  # an image too big or odd to send goes as a file
		if processed_image is not None:
			return self._store_image(name, processed_image)
		if len(data) > MAX_TEXT_BYTES or b"\0" in data:  # a NUL byte means binary
			return None
		try:
			data.decode("utf-8")
		except UnicodeDecodeError:
			return None
		content = AttachmentContent(
			id=uuid.uuid4().hex[:24],
			name=name,
			mime_type=mimetypes.guess_type(name)[0] or "text/plain",
			size=len(data),
			kind="text",
		)
		self._write(content, data)
		return content

	def _store_image(self, name: str, processed: tuple[bytes, str, int, int]) -> AttachmentContent:
		data, mime_type, width, height = processed
		content = AttachmentContent(
			id=uuid.uuid4().hex[:24],
			name=name,
			mime_type=mime_type,
			size=len(data),
			kind="image",
			width=width,
			height=height,
		)
		self._write(content, data)
		return content

	def get(self, attachment_id: str) -> AttachmentContent:
		with self._lock:
			return self._get_unlocked(attachment_id)

	def read(self, attachment_id: str) -> bytes:
		with self._lock:
			self._get_unlocked(attachment_id)
			try:
				with open(self._data_path(attachment_id), "rb") as file:
					return file.read()
			except OSError:
				raise AttachmentError(f"attachment data not found: {attachment_id}") from None

	def claim(self, attachment_ids: list[str]) -> tuple[str, ...]:
		"""Mark attachments as referenced by an admitted message.

		The marker makes cleanup safe when a client cannot tell whether a run request
		reached the daemon. The return value identifies markers created by this call.
		"""
		with self._lock:
			for attachment_id in attachment_ids:
				self._get_unlocked(attachment_id)
			claimed = []
			for attachment_id in attachment_ids:
				if os.path.exists(self._used_path(attachment_id)):
					continue
				_write_private(self._used_path(attachment_id), b"")
				claimed.append(attachment_id)
			return tuple(claimed)

	def discard_claims(self, attachment_ids: tuple[str, ...]) -> None:
		"""Remove newly claimed staging data that never became durable."""
		with self._lock:
			for attachment_id in attachment_ids:
				self._remove_unlocked(attachment_id)

	def remove_unclaimed(self, attachment_ids: list[str]) -> int:
		with self._lock:
			removed = 0
			for attachment_id in attachment_ids:
				if not _ATTACHMENT_ID_RE.fullmatch(attachment_id) or os.path.exists(
					self._used_path(attachment_id)
				):
					continue
				if self._remove_unlocked(attachment_id):
					removed += 1
			return removed

	def remove(self, attachment_id: str) -> bool:
		with self._lock:
			return self._remove_unlocked(attachment_id)

	def remove_all(self) -> None:
		with self._lock:
			try:
				shutil.rmtree(self.path)
			except FileNotFoundError:
				pass

	def _write(self, content: AttachmentContent, data: bytes) -> None:
		with self._lock:
			_write_private(self._data_path(content.id), data)
			try:
				_write_private(self._meta_path(content.id), content.model_dump_json().encode())
			except Exception:
				try:
					os.unlink(self._data_path(content.id))
				except OSError:
					pass
				raise

	def _get_unlocked(self, attachment_id: str) -> AttachmentContent:
		if not _ATTACHMENT_ID_RE.fullmatch(attachment_id):
			raise AttachmentError("invalid attachment id")
		try:
			with open(self._meta_path(attachment_id), encoding="utf-8") as file:
				return AttachmentContent.model_validate(json.load(file))
		except (OSError, ValueError):
			raise AttachmentError(f"attachment not found: {attachment_id}") from None

	def _remove_unlocked(self, attachment_id: str) -> bool:
		if not _ATTACHMENT_ID_RE.fullmatch(attachment_id):
			return False
		removed = False
		for path in (
			self._data_path(attachment_id),
			self._meta_path(attachment_id),
			self._used_path(attachment_id),
		):
			try:
				os.unlink(path)
			except FileNotFoundError:
				continue
			removed = True
		return removed

	def _data_path(self, attachment_id: str) -> str:
		return os.path.join(self.path, f"{attachment_id}.bin")

	def _meta_path(self, attachment_id: str) -> str:
		return os.path.join(self.path, f"{attachment_id}.json")

	def _used_path(self, attachment_id: str) -> str:
		return os.path.join(self.path, f"{attachment_id}.used")


def _safe_name(name: str, *, keep_dirs: bool = False) -> str:
	name = name.replace("\\", "/").strip()
	if not keep_dirs:
		name = name.split("/")[-1]
	name = "".join(char for char in name if char >= " " and char != "\x7f")[:255]
	if not name or name in {".", ".."}:
		raise AttachmentError("attachment needs a valid filename")
	return name


def _check_tools(name: str, data: bytes, tools: Collection[str]) -> None:
	# bash opens any file; read opens text only
	if "bash" not in tools and ("read" not in tools or b"\0" in data[:SNIFF_BYTES]):
		raise AttachmentError(f"{name} can't be opened by this agent")


def _file_type(name: str) -> str:
	return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _process_image(data: bytes) -> tuple[bytes, str, int, int] | None:
	"""Return normalized image bytes, or None when the input is not an image."""
	try:
		with warnings.catch_warnings():
			warnings.simplefilter("error", Image.DecompressionBombWarning)
			image = Image.open(io.BytesIO(data))
	except UnidentifiedImageError:
		return None
	except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as error:
		raise AttachmentError(f"image could not be decoded safely: {error}") from None

	try:
		image_format = image.format
		if image_format not in _SUPPORTED_IMAGE_FORMATS:
			raise AttachmentError(f"unsupported image format: {image_format or 'unknown'}")
		width, height = image.size
		# Inspect header dimensions before load(): compressed pixels must never be
		# expanded in memory until they pass Flow's stricter limit.
		if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
			raise AttachmentError("image dimensions are too large")
		try:
			with warnings.catch_warnings():
				warnings.simplefilter("error", Image.DecompressionBombWarning)
				image.load()
		except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as error:
			raise AttachmentError(f"image could not be decoded safely: {error}") from None

		mime_type = _SUPPORTED_IMAGE_FORMATS[image_format]
		if (
			image_format != "BMP"
			and width <= MAX_IMAGE_DIMENSION
			and height <= MAX_IMAGE_DIMENSION
			and len(data) <= MAX_IMAGE_BYTES
		):
			return data, mime_type, width, height
		if getattr(image, "is_animated", False):
			raise AttachmentError("animated image exceeds the attachment limits")

		image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
		if image.mode not in ("RGB", "RGBA"):
			converted = image.convert("RGBA" if "transparency" in image.info else "RGB")
			image.close()
			image = converted
		for quality in (90, 80, 70, 60, 50):
			output = io.BytesIO()
			if image.mode == "RGBA" or image_format == "BMP":
				image.save(output, format="PNG", optimize=True)
				out_mime = "image/png"
			else:
				image.save(output, format="JPEG", quality=quality, optimize=True)
				out_mime = "image/jpeg"
			encoded = output.getvalue()
			if len(encoded) <= MAX_IMAGE_BYTES:
				return encoded, out_mime, image.width, image.height
			if image.width <= 256 and image.height <= 256:
				break
			image.thumbnail((max(256, image.width * 3 // 4), max(256, image.height * 3 // 4)))
		raise AttachmentError("image could not be resized below the 5 MB limit")
	finally:
		image.close()


def _write_private(path: str, data: bytes) -> None:
	fd, tmp = mkstemp(prefix=f".{os.path.basename(path)}.", dir=os.path.dirname(path))
	try:
		os.chmod(tmp, 0o600)
		with os.fdopen(fd, "wb") as file:
			file.write(data)
		os.replace(tmp, path)
	finally:
		if os.path.exists(tmp):
			os.unlink(tmp)
