import asyncio
import base64
import io
import json
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
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
from flow_harness.model.credentials import CredentialStore
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


def test_attachment_store_add_bytes_takes_only_safe_images(tmp_path, monkeypatch):
	store = AttachmentStore(str(tmp_path / "attachments"))
	data = _png()
	png = store.add_bytes("screenshot.bin", data)  # detected from the bytes, not the name
	metadata = json.loads((tmp_path / "attachments" / f"{png.id}.json").read_text())
	assert (png.kind, png.mime_type, png.width, png.height) == ("image", "image/png", 8, 6)
	assert store.read(png.id) == data
	assert "data" not in metadata  # the bytes stay out of the metadata

	assert store.add_bytes("wide.png", _png(2_500, 10)).width == 2_000
	bmp_data = io.BytesIO()
	Image.new("RGB", (4, 3), "blue").save(bmp_data, format="BMP")
	bmp = store.add_bytes("old.bmp", bmp_data.getvalue())
	assert bmp.mime_type == "image/png"
	assert store.read(bmp.id).startswith(b"\x89PNG")

	for name, body in (("notes.txt", b"hello"), ("archive.bin", b"\x00\xff\x00")):
		try:
			store.add_bytes(name, body)
		except AttachmentError as error:
			assert str(error) == f"{name} is not a supported image"
		else:
			raise AssertionError(f"non-image attachment was accepted: {name}")

	def chunk(kind: bytes, data: bytes) -> bytes:
		checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
		return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

	header = struct.pack(">IIBBBBB", 7_000, 6_000, 8, 2, 0, 0, 0)
	bomb = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")
	# a bomb is refused from its header, before any pixel is decoded
	monkeypatch.setattr(Image.Image, "load", lambda self: (_ for _ in ()).throw(AssertionError("decoded")))
	with pytest.raises(AttachmentError, match="dimensions"):
		store.add_bytes("bomb.png", bomb)


def test_attachment_store_add_file_inlines_what_it_can_and_points_at_the_rest(tmp_path, monkeypatch):
	"""Images and small text go inline; anything else goes by path when the agent can open it:
	bash opens any file, read only text."""
	monkeypatch.setattr(attachment_module, "MAX_IMAGE_DIMENSION", 16)
	frames = [Image.new("RGB", (40, 40), color) for color in ("red", "blue")]
	output = io.BytesIO()
	frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:])
	gif, pdf, png = output.getvalue(), b"%PDF-1.7\n\xff\x00", _png()
	big_text = b"x" * (attachment_module.MAX_TEXT_BYTES + 1)
	store = AttachmentStore(str(tmp_path / "attachments"))

	for name, data, tools, kind, mime_type in (
		("src/notes.txt", b"hello world", (), "text", "text/plain"),  # a mention keeps its directories
		("img/shot", png, (), "image", "image/png"),  # no extension: decided by content
		("big.txt", big_text, {"bash"}, "file", "text/plain"),
		("big.txt", big_text, {"read"}, "file", "text/plain"),
		("docs/q3.pdf", pdf, {"bash"}, "file", "application/pdf"),
		("demo.gif", gif, {"bash"}, "file", "image/gif"),  # an animation over the image limits
	):
		attachment = store.add_file(name, data, tools=tools, path=f"/p/{name}")
		assert (attachment.name, attachment.kind, attachment.mime_type) == (name, kind, mime_type), name
		if kind == "file":  # metadata only: the tools open the project file
			assert attachment.path == f"/p/{name}", name
			assert not (tmp_path / "attachments" / f"{attachment.id}.bin").exists(), name
		else:
			assert store.read(attachment.id) == data, name

	for name, data, tools, error in (
		("empty.txt", b"", {"bash"}, "empty"),
		("report.pdf", pdf, {"read"}, "report.pdf can't be opened by this agent"),
		("report.pdf", pdf, (), "report.pdf can't be opened by this agent"),
		("big.txt", big_text, (), "big.txt can't be opened by this agent"),
	):
		try:
			store.add_file(name, data, tools=tools, path=f"/p/{name}")
		except AttachmentError as exc:
			assert error in str(exc), (name, tools)
		else:
			raise AssertionError(f"{name} was accepted with tools {tools}")
	with pytest.raises(AttachmentError, match="animated image"):
		store.add_bytes("demo.gif", gif)  # an upload has no path to fall back on


def test_user_content_resolves_by_kind_and_image_capability():
	file = AttachmentContent(
		id="a" * 24,
		name="clip.mp4",
		mime_type="video/mp4",
		size=3 * 1024 * 1024,
		kind="file",
		path="/data/clip.mp4",
	)
	image = AttachmentContent(id="b" * 24, name="screen.png", mime_type="image/png", size=3, kind="image")
	message = UserMessage(content=[TextContent(text="what happens here?"), file, image])
	data = {image.id: b"png"}  # a file's bytes are never read
	note = "what happens here?\n[Attached file: clip.mp4 (video/mp4, 3.0 MB)]\n" + FILE_PLACEHOLDER.format(
		path="/data/clip.mp4"
	)

	# an unknown capability sends the image and lets the provider decide
	text, images = resolve_user_content(message, resolve_attachment=data.__getitem__)
	assert text == note
	assert [(i.name, i.mime_type, i.data) for i in images] == [("screen.png", "image/png", b"png")]

	text, images = resolve_user_content(message, resolve_attachment=data.__getitem__, supports_images=False)
	assert images == []
	assert text.startswith(note) and NON_VISION_IMAGE_PLACEHOLDER in text and "screen.png" in text
	result = _tool_result("c1", "screen.png", [image])
	assert resolve_tool_images(result, resolve_attachment=data.__getitem__, supports_images=False) == []
	assert attachment_summary(message) == f"{note}\n[Attached image: screen.png]"  # compaction keeps the path


def test_image_capability_comes_from_the_catalog():
	assert opencode_go_model("opencode-go/kimi-k3", api_key="token").supports_images
	assert not opencode_go_model("opencode-go/deepseek-v4-pro", api_key="token").supports_images
	assert model_supports_images("opencode-go/kimi-k2.6") is True
	assert model_supports_images("codex/gpt-5.6-terra") is True
	assert model_supports_images("custom/gpt-4o") is None
	assert LiteLLMModel("custom/gpt-4o").supports_images is None  # a gateway model stays ungated


def test_attachment_http_upload_preview_claim_and_cleanup(tmp_path):
	data_dir = tmp_path / "data"
	project = tmp_path / "project"
	project.mkdir()
	store = SessionStore(str(data_dir), credential_store=CredentialStore(str(tmp_path / "credentials.json")))
	client = TestClient(create_app(store))
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	image = _png()

	def upload(*files: tuple[str, bytes, str]):
		return client.post(f"/sessions/{sid}/attachments", files=[("files", file) for file in files])

	# one bad file fails the batch and leaves nothing behind
	failed = upload(("screen.png", image, "image/png"), ("notes.txt", b"hello", "text/plain"))
	assert failed.status_code == 400
	assert failed.json() == {"detail": "notes.txt is not a supported image"}
	attachments_dir = next((data_dir / "sessions").rglob(f"{sid}.attachments"))
	assert list(attachments_dir.iterdir()) == []

	used, unused = (
		upload((name, image, "image/png")).json()["attachments"][0]["id"]
		for name in ("used.png", "unused.png")
	)
	preview = client.get(f"/sessions/{sid}/attachments/{used}")
	assert preview.status_code == 200
	assert preview.content == image
	assert preview.headers["content-type"] == "image/png"
	assert preview.headers["cache-control"] == "private, max-age=31536000, immutable"

	# a run claims its attachments on admission, so cleanup removes only the unclaimed one
	started = client.post(f"/sessions/{sid}/run", json={"message": "read", "attachments": [used]})
	assert started.json() == {"status": "started"}
	cleanup = client.request("DELETE", f"/sessions/{sid}/attachments", json={"attachments": [unused, used]})
	assert cleanup.json() == {"removed": 1}
	attachment_store = store.get(sid).attachment_store
	assert attachment_store is not None
	assert attachment_store.read(used) == image
	with pytest.raises(AttachmentError):
		attachment_store.read(unused)

	response = client.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read this", "attachments": [used]},
	)
	assert response.status_code == 200
	entries = client.get(f"/sessions/{sid}/entries").json()["entries"]
	user = next(entry for entry in entries if entry["type"] == "user_message")
	assert user["content"][1]["name"] == "used.png"
	log = next((data_dir / "sessions").rglob(f"{sid}.jsonl"))
	assert base64.b64encode(image).decode() not in log.read_text()  # a reference, not the bytes

	# deleting the session from a cold store removes its attachments and the emptied project folder
	cold = TestClient(create_app(SessionStore(str(data_dir))))
	assert cold.delete(f"/sessions/{sid}").json() == {"status": "deleted"}
	assert not attachments_dir.exists()
	assert not attachments_dir.parent.exists()


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


def test_attach_files_http_reads_project_files_by_path(tmp_path):
	"""The kind comes from the content, not the name; the name is the cwd-relative path."""
	project = tmp_path / "project"
	(project / "src").mkdir(parents=True)
	(project / "src" / "notes.txt").write_text("hello from disk")
	(project / "logo.png").write_bytes(_png())
	(project / "screenshot").write_bytes(_png())  # an image without an extension
	(project / "notes.png").write_text("actually just text")  # text wearing an image name
	credentials = CredentialStore(str(tmp_path / "credentials.json"))
	client = TestClient(create_app(SessionStore(str(tmp_path / "data"), credential_store=credentials)))
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]

	response = client.post(
		f"/sessions/{sid}/attachments/files",
		json={"paths": ["src/notes.txt", "logo.png", "screenshot", "notes.png"]},
	)

	assert response.status_code == 200
	attachments = response.json()["attachments"]
	kinds = [("src/notes.txt", "text"), ("logo.png", "image"), ("screenshot", "image"), ("notes.png", "text")]
	assert [(item["name"], item["kind"]) for item in attachments] == kinds
	logo, screenshot = attachments[1], attachments[2]
	assert (logo["mime_type"], logo["width"], logo["height"]) == ("image/png", 8, 6)
	assert screenshot["mime_type"] == "image/png"

	run = client.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read these", "attachments": [item["id"] for item in attachments]},
	)
	assert run.status_code == 200
	entries = client.get(f"/sessions/{sid}/entries").json()["entries"]
	user = next(entry for entry in entries if entry["type"] == "user_message")
	assert [(item["name"], item["kind"]) for item in user["content"][1:]] == kinds


def test_attach_files_http_points_at_project_files_it_cannot_inline(tmp_path, monkeypatch):
	"""A binary file, or one over the read cap, goes by path if the agent can open it."""
	monkeypatch.setattr(session_routes, "MAX_SOURCE_BYTES", 1024)
	data_dir = tmp_path / "data"
	project = tmp_path / "project"
	project.mkdir()
	(project / "report.pdf").write_bytes(b"%PDF-1.7\n\xff\x00")
	(project / "dump.bin").write_bytes(b"\x00" * 2048)
	(project / "app.log").write_text("x" * 2048)  # over the read cap
	client = TestClient(create_app(SessionStore(str(data_dir))))

	def attach(sid: str, path: str):
		return client.post(f"/sessions/{sid}/attachments/files", json={"paths": [path]})

	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	for path, size in (("report.pdf", 11), ("app.log", 2048)):
		response = attach(sid, path)
		assert response.status_code == 200, path
		[attachment] = response.json()["attachments"]
		assert (attachment["kind"], attachment["size"]) == ("file", size), path
		assert attachment["path"] == str(project / path), path
	attachments_dir = next((data_dir / "sessions").rglob(f"{sid}.attachments"))
	assert {item.suffix for item in attachments_dir.iterdir()} == {".json"}  # metadata only

	# a read-only agent is refused a PDF or a big binary, but gets big text
	read_only = client.post("/sessions", json={"cwd": str(project), "tools": ["read"]}).json()["session_id"]
	for path in ("report.pdf", "dump.bin"):
		response = attach(read_only, path)
		assert response.status_code == 400, path
		assert response.json() == {"detail": f"{path} can't be opened by this agent"}
	big_text = attach(read_only, "app.log")
	assert big_text.status_code == 200
	assert big_text.json()["attachments"][0]["kind"] == "file"


def test_attach_files_http_keeps_nothing_from_a_refused_request(tmp_path):
	allowed = tmp_path / "allowed"
	outside = tmp_path / "outside"
	allowed.mkdir()
	outside.mkdir()
	(allowed / "real.txt").write_text("present")
	(outside / "secret.txt").write_text("nope")
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(allowed)])
	client = TestClient(create_app(store))
	sid = client.post("/sessions", json={"cwd": str(allowed)}).json()["session_id"]
	attachments_dir = next((tmp_path / "data" / "sessions").rglob(f"{sid}.attachments"))

	for paths, status, detail in (
		# the shared explorer fence refuses a path outside the allowed roots
		(["../outside/secret.txt"], 403, "path is outside the allowed roots"),
		(["real.txt", "missing.txt"], 404, "file not found"),  # the partial batch is cleaned up
	):
		response = client.post(f"/sessions/{sid}/attachments/files", json={"paths": paths})
		assert (response.status_code, response.json()) == (status, {"detail": detail}), paths
		assert list(attachments_dir.iterdir()) == [], paths


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


async def test_read_stores_images_by_content_and_returns_only_metadata(tmp_path):
	store = AttachmentStore(str(tmp_path / "attachments"))
	target = tmp_path / "diagram.png"
	target.write_bytes(_png(40, 30))
	(tmp_path / "screenshot").write_bytes(_png())  # an image without an extension
	(tmp_path / "notes.png").write_text("just text")  # text wearing an image name
	# a real signature with no image behind it
	(tmp_path / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"junk")

	async def sink(name: str, data: bytes) -> AttachmentContent:
		return await asyncio.to_thread(store.add_bytes, name, data)

	ctx = ToolContext(cwd=str(tmp_path), store_image=sink)
	result = await read(path=str(target), ctx=ctx)

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

	assert [item.kind for item in (await read(path="screenshot", ctx=ctx)).attachments] == ["image"]
	text = await read(path="notes.png", ctx=ctx)
	assert (text.is_error, text.attachments, text.content) == (False, [], "just text")
	broken = await read(path="broken.png", ctx=ctx)
	assert broken.is_error and broken.attachments == []
	assert "cannot read image" in broken.content

	# no attachment store (an embedded Agent) is not an error; the file is fine
	bare = await read(path=str(target), ctx=ToolContext(cwd=str(tmp_path)))
	assert (bare.is_error, bare.attachments) == (False, [])
	assert "unavailable in this session" in bare.content


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


def test_litellm_wire_inlines_attachments_and_sends_tool_images_after_each_batch(tmp_path):
	"""A tool message must directly follow its call, so a batch's images go out as one user turn
	after the batch, before the next assistant turn."""
	store = AttachmentStore(str(tmp_path / "attachments"))
	notes = store.add_file("notes.txt", b"hello", tools=(), path=str(tmp_path / "notes.txt"))
	screen, first, second, third = (
		_stored(store, name) for name in ("screen.png", "a.png", "b.png", "c.png")
	)
	messages = [
		UserMessage(content=[TextContent(text="review"), notes, screen]),
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read", arguments={}),
				ToolCall(id="c2", name="read", arguments={}),
			],
			stop_reason="tool_use",
		),
		_tool_result("c1", "a.png", [first]),
		_tool_result("c2", "b.png", [second]),
		AssistantMessage(
			content=[TextContent(text="One more."), ToolCall(id="c3", name="read", arguments={})],
			stop_reason="tool_use",
		),
		_tool_result("c3", "c.png", [third]),
	]
	model = LiteLLMModel("openai/gpt-4o")

	wire = _openai_messages(messages, model, "system", resolve_attachment=store.read)

	roles = ["system", "user", "assistant", "tool", "tool", "user", "assistant", "tool", "user"]
	assert [m["role"] for m in wire] == roles
	assert wire[1]["content"][0]["text"] == 'review\n<file name="notes.txt">\nhello\n</file>'
	assert wire[1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
	for turn, count in ((wire[5], 2), (wire[8], 1)):
		assert turn["content"][0] == {"type": "text", "text": _TOOL_IMAGE_PREFACE}
		urls = [part["image_url"]["url"] for part in turn["content"][1:]]
		assert len(urls) == count and all(url.startswith("data:image/png;base64,") for url in urls)

	# bytes that went away are skipped, not fatal: the tool's own text already names the image
	for stored in (first, second, third):
		store.remove(stored.id)
	wire = _openai_messages(messages, model, "system", resolve_attachment=store.read)
	assert [m["role"] for m in wire] == ["system", "user", "assistant", "tool", "tool", "assistant", "tool"]


def test_codex_wire_sends_images_as_input_image_blocks(tmp_path):
	"""User images go in the message; tool images go inside the function call's output."""
	store = AttachmentStore(str(tmp_path / "attachments"))
	screen, shot = _stored(store, "screen.png"), _stored(store)
	messages = [
		UserMessage(content=[TextContent(text="review"), screen]),
		AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={})], stop_reason="tool_use"),
		_tool_result("c1", "shot.png", [shot]),
	]

	items = _responses_input(
		messages, CodexModel("codex/gpt-5.4", api_key="token"), resolve_attachment=store.read
	)

	user, output = items[0]["content"], items[-1]
	assert user[0] == {"type": "input_text", "text": "review"}
	assert output["type"] == "function_call_output"
	assert output["output"][0] == {"type": "input_text", "text": "[Image: shot.png]"}
	for block in (user[1], output["output"][1]):
		assert block["type"] == "input_image"
		assert block["image_url"].startswith("data:image/png;base64,")
