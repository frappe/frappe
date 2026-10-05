import asyncio
import base64
import io
import json
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient
from PIL import Image

from flow_harness.events import (
	AssistantMessage,
	AttachmentContent,
	TextContent,
	ToolCall,
	ToolResult,
	Usage,
	UserMessage,
)
from flow_harness.model.base import Model
from flow_harness.model.catalog import model_supports_images
from flow_harness.model.content import (
	FILE_PLACEHOLDER,
	NON_VISION_IMAGE_PLACEHOLDER,
	attachment_summary,
	resolve_tool_images,
	resolve_user_content,
)
from flow_harness.model.litellm import _TOOL_IMAGE_PREFACE, LiteLLMModel, _openai_messages
from flow_harness.model.mock import MockModel
from flow_harness.model.providers.codex import CodexModel, _responses_input
from flow_harness.model.providers.opencode import opencode_go_model
from flow_harness.server import create_app
from flow_harness.server.routes import sessions as session_routes
from flow_harness.session import attachments as attachment_module
from flow_harness.session.attachments import AttachmentError, AttachmentStore
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_harness.tools.builtins.read import read
from flow_harness.tools.tool import ToolContext


def _png(width: int = 8, height: int = 6) -> bytes:
	output = io.BytesIO()
	Image.new("RGB", (width, height), "red").save(output, format="PNG")
	return output.getvalue()


def test_attachment_store_keeps_bytes_out_of_metadata(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	data = _png()
	attachment = store.add_bytes("screen.png", data)
	metadata = json.loads((tmp_path / "attachments" / f"{attachment.id}.json").read_text())

	assert attachment.kind == "image"
	assert store.read(attachment.id) == data
	assert "data" not in metadata


def test_attachment_store_detects_images_from_bytes(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	attachment = store.add_bytes("screenshot.bin", _png())

	assert attachment.kind == "image"
	assert attachment.mime_type == "image/png"
	assert (attachment.width, attachment.height) == (8, 6)


def test_attachment_store_resizes_large_images_and_converts_bmp(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	large = store.add_bytes("wide.png", _png(2_500, 10))
	bmp_data = io.BytesIO()
	Image.new("RGB", (4, 3), "blue").save(bmp_data, format="BMP")
	bmp = store.add_bytes("old.bmp", bmp_data.getvalue())

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
		store.add_bytes("bomb.png", compressed)
	except AttachmentError as error:
		assert "dimensions" in str(error)
	else:
		raise AssertionError("oversized image was accepted")


def test_attachment_store_rejects_non_images(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	for name, data in (("notes.txt", b"hello"), ("archive.bin", b"\x00\xff\x00")):
		try:
			store.add_bytes(name, data)
		except AttachmentError as error:
			assert str(error) == f"{name} is not a supported image"
		else:
			raise AssertionError(f"non-image attachment was accepted: {name}")


def test_attachment_store_add_file_keeps_the_path_and_decides_by_content(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	attachment = store.add_file(
		"src/notes.txt", b"hello world", tools=(), path=str(tmp_path / "src/notes.txt")
	)

	assert attachment.kind == "text"
	assert attachment.name == "src/notes.txt"  # mentions keep their directories
	assert attachment.mime_type == "text/plain"
	assert store.read(attachment.id) == b"hello world"

	image = store.add_file("img/shot", _png(), tools=(), path=str(tmp_path / "img/shot"))  # no extension
	assert (image.kind, image.name, image.mime_type) == ("image", "img/shot", "image/png")


def test_attachment_store_points_at_what_cannot_go_inline(tmp_path):
	"""Big text and binary are not copied: the model's tools open the project file."""
	store = AttachmentStore(str(tmp_path / "attachments"))
	try:
		store.add_file("empty.txt", b"", tools={"bash"}, path="/project/empty.txt")
	except AttachmentError as error:
		assert "empty" in str(error)
	else:
		raise AssertionError("empty attachment was accepted")

	big_text = b"x" * (attachment_module.MAX_TEXT_BYTES + 1)
	big = store.add_file("big.txt", big_text, tools={"bash"}, path="/project/big.txt")
	pdf = store.add_file("docs/q3.pdf", b"%PDF-1.7\n\xff\x00", tools={"bash"}, path="/project/docs/q3.pdf")

	assert (big.kind, big.path) == ("file", "/project/big.txt")
	assert (pdf.kind, pdf.mime_type, pdf.path) == ("file", "application/pdf", "/project/docs/q3.pdf")
	assert {item.suffix for item in (tmp_path / "attachments").iterdir()} == {".json"}  # metadata only


def test_a_file_the_agent_cannot_open_is_refused(tmp_path):
	"""bash opens any file and read only text; with neither, only what goes inline is taken."""
	store = AttachmentStore(str(tmp_path / "attachments"))
	pdf = b"%PDF-1.7\n\xff\x00"
	big_text = b"x" * (attachment_module.MAX_TEXT_BYTES + 1)

	assert store.add_file("report.pdf", pdf, tools={"bash"}, path="/p/report.pdf").kind == "file"
	assert store.add_file("big.txt", big_text, tools={"read"}, path="/p/big.txt").kind == "file"
	for name, data, tools in (
		("report.pdf", pdf, {"read"}),
		("report.pdf", pdf, ()),
		("big.txt", big_text, ()),
	):
		try:
			store.add_file(name, data, tools=tools, path=f"/p/{name}")
		except AttachmentError as error:
			assert str(error) == f"{name} can't be opened by this agent"
		else:
			raise AssertionError(f"{name} was accepted with tools {tools}")


def test_a_mentioned_animation_too_big_to_send_goes_by_path(tmp_path, monkeypatch):
	"""A GIF over the image limits is pointed at instead of failing; an upload still errors."""
	monkeypatch.setattr(attachment_module, "MAX_IMAGE_DIMENSION", 16)
	frames = [Image.new("RGB", (40, 40), color) for color in ("red", "blue")]
	output = io.BytesIO()
	frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:])
	store = AttachmentStore(str(tmp_path / "attachments"))

	attachment = store.add_file("demo.gif", output.getvalue(), tools={"bash"}, path="/p/demo.gif")

	assert (attachment.kind, attachment.mime_type) == ("file", "image/gif")
	try:
		store.add_bytes("demo.gif", output.getvalue())
	except AttachmentError as error:
		assert "animated image" in str(error)
	else:
		raise AssertionError("an oversized animation upload was accepted")


def test_a_file_reaches_the_model_as_a_note_with_its_path():
	attachment = AttachmentContent(
		id="a" * 24,
		name="clip.mp4",
		mime_type="video/mp4",
		size=3 * 1024 * 1024,
		kind="file",
		path="/data/clip.mp4",
	)
	message = UserMessage(content=[TextContent(text="what happens here?"), attachment])

	def unread(_: str) -> bytes:
		raise AssertionError("a file's bytes were read")

	text, images = resolve_user_content(message, resolve_attachment=unread)

	assert images == []
	assert text == (
		"what happens here?\n[Attached file: clip.mp4 (video/mp4, 3.0 MB)]\n"
		+ FILE_PLACEHOLDER.format(path="/data/clip.mp4")
	)
	assert attachment_summary(message) == text  # compaction keeps the path


def test_images_resolve_when_capability_is_unknown():
	attachment = AttachmentContent(
		id="a" * 24,
		name="screen.png",
		mime_type="image/png",
		size=3,
		kind="image",
	)
	message = UserMessage(content=[TextContent(text="inspect this"), attachment])
	text, images = resolve_user_content(message, resolve_attachment=lambda _: b"png")

	assert [(image.name, image.mime_type, image.data) for image in images] == [
		("screen.png", "image/png", b"png")
	]
	assert text == "inspect this"


def test_known_non_vision_model_gets_image_placeholder():
	attachment = AttachmentContent(
		id="a" * 24, name="screen.png", mime_type="image/png", size=3, kind="image"
	)
	message = UserMessage(content=[TextContent(text="inspect this"), attachment])
	text, images = resolve_user_content(message, resolve_attachment=lambda _: b"png", supports_images=False)

	assert images == []
	assert NON_VISION_IMAGE_PLACEHOLDER in text and "screen.png" in text
	result = _tool_result("c1", "shot.png", [attachment])
	assert resolve_tool_images(result, resolve_attachment=lambda _: b"png", supports_images=False) == []
	assert LiteLLMModel("custom/gpt-4o").supports_images is None  # a gateway model stays ungated


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
			files=[("files", (name, _png(), "image/png"))],
		)
		return response.json()["attachments"][0]["id"]

	unused = upload("unused.png")
	used = upload("used.png")
	client.post(f"/sessions/{sid}/run", json={"message": "read", "attachments": [used]})
	response = client.request(
		"DELETE",
		f"/sessions/{sid}/attachments",
		json={"attachments": [unused, used]},
	)

	assert response.json() == {"removed": 1}
	session = store.get(sid)
	assert session.attachment_store is not None
	assert session.attachment_store.read(used) == _png()
	try:
		session.attachment_store.read(unused)
	except AttachmentError:
		pass
	else:
		raise AssertionError("unclaimed attachment was retained")


def test_cold_session_delete_removes_attachments_and_empty_project_directory(tmp_path):
	data_dir = tmp_path / "data"
	project = tmp_path / "project"
	project.mkdir()
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	uploaded = client.post(
		f"/sessions/{sid}/attachments",
		files=[("files", ("screen.png", _png(), "image/png"))],
	)
	assert uploaded.status_code == 200
	session = store.get(sid)
	assert session.attachment_store is not None
	attachments_dir = Path(session.attachment_store.path)
	project_dir = attachments_dir.parent
	assert any(attachments_dir.iterdir())

	cold = TestClient(create_app(SessionStore(str(data_dir))))
	assert cold.delete(f"/sessions/{sid}").json() == {"status": "deleted"}

	assert not attachments_dir.exists()
	assert not project_dir.exists()


def test_claim_and_cleanup_are_atomic(tmp_path, monkeypatch):
	store = AttachmentStore(str(tmp_path / "attachments"))
	data = _png()
	attachment = store.add_bytes("screen.png", data)
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

	assert store.read(attachment.id) == data


def test_attachment_http_rejects_non_images_and_cleans_partial_batch(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	sid = client.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]

	response = client.post(
		f"/sessions/{sid}/attachments",
		files=[
			("files", ("screen.png", _png(), "image/png")),
			("files", ("notes.txt", b"hello", "text/plain")),
		],
	)

	assert response.status_code == 400
	assert response.json() == {"detail": "notes.txt is not a supported image"}
	attachments_dir = next((data_dir / "sessions").rglob(f"{sid}.attachments"))
	assert list(attachments_dir.iterdir()) == []


def test_attachment_http_flow_persists_reference_not_bytes(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	project = tmp_path / "project"
	project.mkdir()

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	image = _png()
	uploaded = client.post(
		f"/sessions/{sid}/attachments",
		files=[("files", ("screen.png", image, "image/png"))],
	)
	assert uploaded.status_code == 200
	attachment = uploaded.json()["attachments"][0]
	preview = client.get(f"/sessions/{sid}/attachments/{attachment['id']}")
	assert preview.status_code == 200
	assert preview.content == image
	assert preview.headers["content-type"] == "image/png"
	assert preview.headers["cache-control"] == "private, max-age=31536000, immutable"

	response = client.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read this", "attachments": [attachment["id"]]},
	)
	assert response.status_code == 200
	entries = client.get(f"/sessions/{sid}/entries").json()["entries"]
	user = next(entry for entry in entries if entry["type"] == "user_message")
	assert user["content"][1]["name"] == "screen.png"
	log = next((data_dir / "sessions").rglob(f"{sid}.jsonl"))
	assert base64.b64encode(image).decode() not in log.read_text()


def test_attach_files_http_reads_project_files_by_path(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	project = tmp_path / "project"
	project.mkdir()
	(project / "src").mkdir()
	(project / "src" / "notes.txt").write_text("hello from disk")

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	response = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["src/notes.txt"]})

	assert response.status_code == 200
	attachment = response.json()["attachments"][0]
	assert attachment["kind"] == "text"
	assert attachment["name"] == "src/notes.txt"  # the cwd-relative path, not the basename

	run = client.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read this", "attachments": [attachment["id"]]},
	)
	assert run.status_code == 200
	entries = client.get(f"/sessions/{sid}/entries").json()["entries"]
	user = next(entry for entry in entries if entry["type"] == "user_message")
	assert user["content"][1]["name"] == "src/notes.txt"


def test_attach_files_http_classifies_by_content_not_extension(tmp_path):
	"""A filename is not evidence of type: an extensionless image still attaches as one,
	and a .png that holds text is stored as text rather than failing the image sniff."""
	store = SessionStore(str(tmp_path / "data"))
	client = TestClient(create_app(store))
	project = tmp_path / "project"
	project.mkdir()
	(project / "screenshot").write_bytes(_png())  # image, no extension
	(project / "notes.png").write_text("actually just text")  # text wearing an image name

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	response = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["screenshot", "notes.png"]})

	assert response.status_code == 200
	by_name = {item["name"]: item for item in response.json()["attachments"]}
	assert by_name["screenshot"]["kind"] == "image"
	assert by_name["screenshot"]["mime_type"] == "image/png"
	assert by_name["notes.png"]["kind"] == "text"


def test_attach_files_http_reads_image_files_by_extension(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	project = tmp_path / "project"
	project.mkdir()
	(project / "logo.png").write_bytes(_png())

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	response = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["logo.png"]})

	assert response.status_code == 200
	attachment = response.json()["attachments"][0]
	assert attachment["kind"] == "image"
	assert attachment["mime_type"] == "image/png"
	assert (attachment["width"], attachment["height"]) == (8, 6)

	run = client.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "what is this", "attachments": [attachment["id"]]},
	)
	assert run.status_code == 200
	entries = client.get(f"/sessions/{sid}/entries").json()["entries"]
	user = next(entry for entry in entries if entry["type"] == "user_message")
	assert user["content"][1]["kind"] == "image"


def test_attach_files_http_points_at_project_files_it_cannot_inline(tmp_path, monkeypatch):
	"""A binary file, or one over the read cap, goes by path and nothing is copied."""
	monkeypatch.setattr(session_routes, "MAX_SOURCE_BYTES", 1024)
	data_dir = tmp_path / "data"
	client = TestClient(create_app(SessionStore(str(data_dir))))
	project = tmp_path / "project"
	project.mkdir()
	(project / "report.pdf").write_bytes(b"%PDF-1.7\n\xff\x00")
	(project / "app.log").write_text("x" * 2048)  # over the read cap

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	response = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["report.pdf"]})
	too_big = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["app.log"]})

	assert response.status_code == 200
	[pdf] = response.json()["attachments"]
	assert (pdf["kind"], pdf["path"]) == ("file", str(project / "report.pdf"))
	assert too_big.status_code == 200
	[log] = too_big.json()["attachments"]
	assert (log["kind"], log["size"], log["path"]) == ("file", 2048, str(project / "app.log"))
	attachments_dir = next((data_dir / "sessions").rglob(f"{sid}.attachments"))
	assert {item.suffix for item in attachments_dir.iterdir()} == {".json"}  # metadata only


def test_attachment_http_refuses_a_file_the_agent_cannot_open(tmp_path, monkeypatch):
	"""A read-only agent is refused a PDF or a big binary, but gets big text."""
	monkeypatch.setattr(session_routes, "MAX_SOURCE_BYTES", 1024)
	project = tmp_path / "project"
	project.mkdir()
	(project / "report.pdf").write_bytes(b"%PDF-1.7\n\xff\x00")
	(project / "dump.bin").write_bytes(b"\x00" * 2048)
	(project / "app.log").write_text("x" * 2048)
	client = TestClient(create_app(SessionStore(str(tmp_path / "data"))))
	sid = client.post("/sessions", json={"cwd": str(project), "tools": ["read"]}).json()["session_id"]

	pdf = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["report.pdf"]})
	big_binary = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["dump.bin"]})
	big_text = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["app.log"]})

	assert pdf.status_code == 400
	assert pdf.json() == {"detail": "report.pdf can't be opened by this agent"}
	assert big_binary.status_code == 400
	assert big_binary.json() == {"detail": "dump.bin can't be opened by this agent"}
	assert big_text.status_code == 200
	assert big_text.json()["attachments"][0]["kind"] == "file"


def test_attach_files_http_rejects_path_outside_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	outside = tmp_path / "outside"
	allowed.mkdir()
	outside.mkdir()
	(outside / "secret.txt").write_text("nope")
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(allowed)])
	client = TestClient(create_app(store))

	sid = client.post("/sessions", json={"cwd": str(allowed)}).json()["session_id"]
	response = client.post(f"/sessions/{sid}/attachments/files", json={"paths": ["../outside/secret.txt"]})

	# the shared explorer fence answers 403 for a path outside the allowed roots
	assert response.status_code == 403
	attachments_dir = next((tmp_path / "data" / "sessions").rglob(f"{sid}.attachments"))
	assert list(attachments_dir.iterdir()) == []


def test_attach_files_http_cleans_up_partial_batch_on_missing_file(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	client = TestClient(create_app(store))
	project = tmp_path / "project"
	project.mkdir()
	(project / "real.txt").write_text("present")

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	response = client.post(
		f"/sessions/{sid}/attachments/files",
		json={"paths": ["real.txt", "missing.txt"]},
	)

	assert response.status_code == 404
	assert response.json() == {"detail": "file not found"}
	attachments_dir = next((data_dir / "sessions").rglob(f"{sid}.attachments"))
	assert list(attachments_dir.iterdir()) == []


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
	attachment = session.attachment_store.add_bytes("later.png", _png())

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


# --- images produced by a tool ---------------------------------------------


def _tool_result(cid: str, name: str, attachments: list[AttachmentContent]) -> ToolResult:
	return ToolResult(tool_call_id=cid, name="read", content=f"[Image: {name}]", attachments=attachments)


def _stored(store: AttachmentStore, name: str = "shot.png") -> AttachmentContent:
	return store.add_bytes(name, _png())


async def test_read_stores_an_image_and_returns_only_metadata(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	target = tmp_path / "diagram.png"
	target.write_bytes(_png(40, 30))

	async def sink(name: str, data: bytes) -> AttachmentContent:
		return await asyncio.to_thread(store.add_bytes, name, data)

	result = await read(path=str(target), ctx=ToolContext(cwd=str(tmp_path), store_image=sink))

	assert not result.is_error
	[stored] = result.attachments
	assert (stored.name, stored.mime_type, stored.width, stored.height) == (
		"diagram.png",
		"image/png",
		40,
		30,
	)
	assert store.read(stored.id) == target.read_bytes()
	# the model sees a summary, never the bytes
	assert result.content == f"[Image: {target} (image/png, 40x30)]"
	assert "base64" not in result.content


async def test_read_image_without_a_store_degrades_to_text(tmp_path):
	target = tmp_path / "diagram.png"
	target.write_bytes(_png())

	result = await read(path=str(target), ctx=ToolContext(cwd=str(tmp_path)))

	# no attachment store (an embedded Agent) is not an error; the file is fine
	assert not result.is_error
	assert result.attachments == []
	assert "unavailable in this session" in result.content


async def test_read_sniffs_images_by_content_not_name(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	(tmp_path / "screenshot").write_bytes(_png())  # image, no extension
	(tmp_path / "notes.png").write_text("just text")  # text wearing an image name

	async def sink(name: str, data: bytes) -> AttachmentContent:
		return await asyncio.to_thread(store.add_bytes, name, data)

	ctx = ToolContext(cwd=str(tmp_path), store_image=sink)
	image = await read(path="screenshot", ctx=ctx)
	text = await read(path="notes.png", ctx=ctx)

	assert [item.kind for item in image.attachments] == ["image"]
	assert not text.is_error and text.attachments == []
	assert text.content == "just text"


async def test_read_reports_a_broken_image_as_an_error(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	target = tmp_path / "broken.png"
	target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"junk")  # a real signature, no image behind it

	async def sink(name: str, data: bytes) -> AttachmentContent:
		return await asyncio.to_thread(store.add_bytes, name, data)

	result = await read(path=str(target), ctx=ToolContext(cwd=str(tmp_path), store_image=sink))

	assert result.is_error
	assert result.attachments == []
	assert "cannot read image" in result.content


async def test_tool_image_bytes_never_reach_the_session_log(tmp_path):
	image = _png(40, 30)
	(tmp_path / "diagram.png").write_bytes(image)
	store = SessionStore(str(tmp_path / "data"))
	session = store.create(SessionConfig(cwd=str(tmp_path)))
	call = AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "diagram.png"})])
	model = MockModel(replies=[call, AssistantMessage(content="that is a diagram")])

	handle = await session.run("read diagram.png", model=model)
	assert handle.task is not None
	await handle.task

	[result] = [m for m in session.transcript.messages if isinstance(m, ToolResult)]
	[stored] = result.attachments
	assert stored.mime_type == "image/png"

	log = next((tmp_path / "data" / "sessions").rglob(f"{session.id}.jsonl")).read_text()
	assert base64.b64encode(image).decode() not in log
	assert stored.id in log  # the reference is there, the bytes are not


def test_litellm_wire_sends_tool_result_images_after_the_result(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	stored = _stored(store)
	messages = [
		AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={})], stop_reason="tool_use"),
		_tool_result("c1", "shot.png", [stored]),
	]

	wire = _openai_messages(messages, LiteLLMModel("openai/gpt-4o"), "system", resolve_attachment=store.read)

	assert [m["role"] for m in wire] == ["system", "assistant", "tool", "user"]
	parts = wire[-1]["content"]
	assert parts[0] == {"type": "text", "text": _TOOL_IMAGE_PREFACE}
	assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_codex_wire_puts_tool_result_images_inside_the_output(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	stored = _stored(store)
	messages = [
		AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={})], stop_reason="tool_use"),
		_tool_result("c1", "shot.png", [stored]),
	]

	items = _responses_input(
		messages, CodexModel("codex/gpt-5.4", api_key="token"), resolve_attachment=store.read
	)

	output = items[-1]
	assert output["type"] == "function_call_output"
	assert output["output"][0] == {"type": "input_text", "text": "[Image: shot.png]"}
	assert output["output"][1]["type"] == "input_image"
	assert output["output"][1]["image_url"].startswith("data:image/png;base64,")


def test_tool_images_flush_once_after_a_batch_of_results(tmp_path):
	"""Inline images would split the tool batch, which the provider rejects."""
	store = AttachmentStore(str(tmp_path / "attachments"))
	first, second = _stored(store, "a.png"), _stored(store, "b.png")
	messages = [
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read", arguments={}),
				ToolCall(id="c2", name="read", arguments={}),
			],
			stop_reason="tool_use",
		),
		_tool_result("c1", "a.png", [first]),
		_tool_result("c2", "b.png", [second]),
	]

	wire = _openai_messages(messages, LiteLLMModel("openai/gpt-4o"), "system", resolve_attachment=store.read)

	# both tool results stay adjacent to their call; one user turn carries both images
	assert [m["role"] for m in wire] == ["system", "assistant", "tool", "tool", "user"]
	images = [p for p in wire[-1]["content"] if p["type"] == "image_url"]
	assert len(images) == 2


def test_tool_images_flush_before_the_next_assistant_turn(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	stored = _stored(store)
	messages = [
		AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={})], stop_reason="tool_use"),
		_tool_result("c1", "shot.png", [stored]),
		AssistantMessage(content="I can see it."),
	]

	wire = _openai_messages(messages, LiteLLMModel("openai/gpt-4o"), "system", resolve_attachment=store.read)

	# the images land before the reply, not stranded at the end of the conversation
	assert [m["role"] for m in wire] == ["system", "assistant", "tool", "user", "assistant"]


def test_missing_tool_image_bytes_are_skipped_not_fatal(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	stored = _stored(store)
	store.remove(stored.id)  # the bytes went away; the event still references them
	messages = [
		AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={})], stop_reason="tool_use"),
		_tool_result("c1", "shot.png", [stored]),
	]

	wire = _openai_messages(messages, LiteLLMModel("openai/gpt-4o"), "system", resolve_attachment=store.read)

	# no image turn, no crash: the tool's own text already names what it read
	assert [m["role"] for m in wire] == ["system", "assistant", "tool"]
