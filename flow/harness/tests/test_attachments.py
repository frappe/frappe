import asyncio
import io
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

from fastapi.testclient import TestClient
from PIL import Image

from flow.events import AssistantMessage, AttachmentContent, TextContent, Usage, UserMessage
from flow.model.base import Model
from flow.model.catalog import model_supports_images
from flow.model.content import NON_VISION_IMAGE_PLACEHOLDER, resolve_user_content
from flow.model.litellm import LiteLLMModel, _openai_messages
from flow.model.providers.codex import CodexModel, _responses_input
from flow.model.providers.opencode import opencode_go_model
from flow.server import create_app
from flow.session import attachments as attachment_module
from flow.session.attachments import AttachmentError, AttachmentStore
from flow.session.config import SessionConfig
from flow.session.store import SessionStore


def _png(width: int = 8, height: int = 6) -> bytes:
	output = io.BytesIO()
	Image.new("RGB", (width, height), "red").save(output, format="PNG")
	return output.getvalue()


def test_attachment_store_keeps_bytes_out_of_metadata(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	attachment = store.add_bytes("notes.txt", b"hello", "text/plain")

	assert attachment.kind == "text"
	assert store.read(attachment.id) == b"hello"
	assert "hello" not in (tmp_path / "attachments" / f"{attachment.id}.json").read_text()


def test_attachment_store_detects_images_from_bytes(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	attachment = store.add_bytes("screenshot.bin", _png(), "application/octet-stream")

	assert attachment.kind == "image"
	assert attachment.mime_type == "image/png"
	assert (attachment.width, attachment.height) == (8, 6)


def test_attachment_store_resizes_large_images_and_converts_bmp(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	large = store.add_bytes("wide.png", _png(2_500, 10), "image/png")
	bmp_data = io.BytesIO()
	Image.new("RGB", (4, 3), "blue").save(bmp_data, format="BMP")
	bmp = store.add_bytes("old.bmp", bmp_data.getvalue(), "image/bmp")

	assert large.width == 2_000
	assert bmp.mime_type == "image/png"
	assert store.read(bmp.id).startswith(b"\x89PNG")


def test_attachment_store_rejects_oversized_dimensions_before_decode(tmp_path, monkeypatch):
	def chunk(kind: bytes, data: bytes) -> bytes:
		checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
		return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

	header = struct.pack(">IIBBBBB", 7_000, 6_000, 8, 2, 0, 0, 0)
	compressed = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")
	monkeypatch.setattr(Image.Image, "load", lambda self: (_ for _ in ()).throw(AssertionError("decoded")))

	store = AttachmentStore(str(tmp_path / "attachments"))
	try:
		store.add_bytes("bomb.png", compressed, "image/png")
	except AttachmentError as error:
		assert "dimensions" in str(error)
	else:
		raise AssertionError("oversized image was accepted")


def test_attachment_store_rejects_binary_files(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	try:
		store.add_bytes("archive.bin", b"\x00\xff\x00")
	except AttachmentError as error:
		assert "supported text or image" in str(error)
	else:
		raise AssertionError("binary attachment was accepted")


def test_non_vision_model_gets_explicit_image_placeholder():
	attachment = AttachmentContent(
		id="a" * 24,
		name="screen.png",
		mime_type="image/png",
		size=3,
		kind="image",
	)
	message = UserMessage(content=[TextContent(text="inspect this"), attachment])
	text, images = resolve_user_content(
		message,
		resolve_attachment=lambda _: b"png",
		supports_images=False,
	)

	assert images == []
	assert NON_VISION_IMAGE_PLACEHOLDER in text
	assert "screen.png" in text


def test_litellm_wire_contains_text_file_and_image_data_url():
	text_attachment = AttachmentContent(
		id="a" * 24,
		name="notes.txt",
		mime_type="text/plain",
		size=5,
		kind="text",
	)
	image_attachment = AttachmentContent(
		id="b" * 24,
		name="screen.png",
		mime_type="image/png",
		size=3,
		kind="image",
	)
	message = UserMessage(content=[TextContent(text="review"), text_attachment, image_attachment])
	data = {text_attachment.id: b"hello", image_attachment.id: b"png"}
	wire = _openai_messages(
		[message],
		LiteLLMModel("openai/gpt-4o"),
		"system",
		resolve_attachment=data.__getitem__,
	)[1]

	assert wire["content"][0]["text"] == 'review\n<file name="notes.txt">\nhello\n</file>'
	assert wire["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_codex_wire_uses_responses_image_blocks():
	attachment = AttachmentContent(
		id="a" * 24,
		name="screen.png",
		mime_type="image/png",
		size=3,
		kind="image",
	)
	message = UserMessage(content=[TextContent(text="review"), attachment])
	items = _responses_input(
		[message],
		CodexModel("codex/gpt-5.4", api_key="token"),
		resolve_attachment=lambda _: b"png",
	)

	assert items[0]["content"][0] == {"type": "input_text", "text": "review"}
	assert items[0]["content"][1]["type"] == "input_image"
	assert items[0]["content"][1]["image_url"].startswith("data:image/png;base64,")


def test_opencode_runtime_uses_catalog_image_capability():
	assert opencode_go_model("opencode-go/kimi-k3", api_key="token").supports_images
	assert not opencode_go_model("opencode-go/deepseek-v4-pro", api_key="token").supports_images
	assert model_supports_images("opencode-go/kimi-k2.6") is True
	assert model_supports_images("codex/gpt-5.6-terra") is True
	assert model_supports_images("custom/gpt-4o") is None


def test_cleanup_removes_only_unclaimed_attachments(tmp_path):
	store = SessionStore(str(tmp_path / "data"))
	client = TestClient(create_app(store))
	sid = client.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]

	def upload(name: str) -> str:
		response = client.post(
			f"/sessions/{sid}/attachments",
			files=[("files", (name, b"contents", "text/plain"))],
		)
		return response.json()["attachments"][0]["id"]

	unused = upload("unused.txt")
	used = upload("used.txt")
	client.post(f"/sessions/{sid}/run", json={"message": "read", "attachments": [used]})
	response = client.request(
		"DELETE",
		f"/sessions/{sid}/attachments",
		json={"attachments": [unused, used]},
	)

	assert response.json() == {"removed": 1}
	session = store.get(sid)
	assert session.attachment_store is not None
	assert session.attachment_store.read(used) == b"contents"
	try:
		session.attachment_store.read(unused)
	except AttachmentError:
		pass
	else:
		raise AssertionError("unclaimed attachment was retained")


def test_claim_and_cleanup_are_atomic(tmp_path, monkeypatch):
	store = AttachmentStore(str(tmp_path / "attachments"))
	attachment = store.add_bytes("notes.txt", b"contents", "text/plain")
	claim_started = Event()
	finish_claim = Event()
	real_write_private = attachment_module._write_private

	def paused_write(path: str, data: bytes) -> None:
		if path.endswith(".used"):
			claim_started.set()
			assert finish_claim.wait(timeout=2)
		real_write_private(path, data)

	monkeypatch.setattr(attachment_module, "_write_private", paused_write)
	with ThreadPoolExecutor(max_workers=2) as executor:
		claim = executor.submit(store.claim, [attachment.id])
		assert claim_started.wait(timeout=2)
		cleanup = executor.submit(store.remove_unclaimed, [attachment.id])
		try:
			cleanup.result(timeout=0.05)
		except TimeoutError:
			pass
		else:
			raise AssertionError("cleanup did not wait for the in-flight claim")
		finish_claim.set()
		claim.result(timeout=2)
		assert cleanup.result(timeout=2) == 0

	assert store.read(attachment.id) == b"contents"


def test_attachment_http_flow_persists_reference_not_bytes(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	project = tmp_path / "project"
	project.mkdir()

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	uploaded = client.post(
		f"/sessions/{sid}/attachments",
		files=[("files", ("notes.txt", b"hello attachment", "text/plain"))],
	)
	assert uploaded.status_code == 200
	attachment = uploaded.json()["attachments"][0]

	response = client.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read this", "attachments": [attachment["id"]]},
	)
	assert response.status_code == 200
	entries = client.get(f"/sessions/{sid}/entries").json()["entries"]
	user = next(entry for entry in entries if entry["type"] == "user_message")
	assert user["content"][1]["name"] == "notes.txt"
	assert "hello attachment" not in (data_dir / "sessions" / f"{sid}.jsonl").read_text()


async def test_abort_discards_undelivered_steering_attachments(tmp_path):
	class BlockingModel(Model):
		name = "blocking"

		def __init__(self):
			self.started = asyncio.Event()
			self.release = asyncio.Event()

		async def run(self, request):
			self.started.set()
			await self.release.wait()
			yield AssistantMessage(content="done")
			yield Usage()

	store = SessionStore(str(tmp_path / "data"))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	model = BlockingModel()
	run = await session.run("start", model=model)
	await asyncio.wait_for(model.started.wait(), timeout=2)
	assert session.attachment_store is not None
	attachment = session.attachment_store.add_bytes("later.txt", b"later", "text/plain")

	steering = await session.run("use this later", attachment_ids=[attachment.id])
	assert steering.status == "steered"
	assert session.abort()
	model.release.set()
	assert run.task is not None
	await asyncio.wait_for(run.task, timeout=2)

	try:
		session.attachment_store.read(attachment.id)
	except AttachmentError:
		pass
	else:
		raise AssertionError("aborted undelivered steering attachment was retained")
