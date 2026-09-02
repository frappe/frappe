# File Storage v2 for Frappe Framework

Draft spec for review. Based on code analysis of frappe v17.0.0-dev
(agents mapped the current module; refs are in that report).

## Goal

Add a modern file storage module behind a per-site feature flag.

- Pluggable storage drivers, for reads and writes.
- A blob table: one row per stored object, refcounted, garbage-collected.
- Signed, expiring URLs for private files.
- Direct-to-storage and resumable uploads.
- Content sniffing instead of extension trust.
- A storage fake for tests.

## Non-goals (v1)

- Image variants and thumbnails. Keep the current `make_thumbnail`.
- Folder tree changes. The `File` folder fields stay as they are.
- Migrating writers that bypass `File` (website theme, chromium screenshots).
- Changing public website asset serving. nginx keeps serving `/files/`.

## Feature flag

Site config key: `storage_v2` (bool, default off).

- Off: nothing changes. All current paths run as today.
- On: new uploads create a `File Blob` row and route through a driver.
  Reads resolve both old and new rows, so the flag is safe to enable
  on an existing site.

## Architecture

Four layers. Each layer only calls the one below it.

```
File (attachment row)      links doc <-> blob, owns permissions
File Blob (blob row)       checksum, size, driver, key, refcount source
StorageDriver              read/write/delete/exists bytes by key
HTTP                       signed URLs, serve route, direct upload
```

## Data model

### New doctype: `File Blob`

| field | type | notes |
|---|---|---|
| `key` | Data | driver-scoped object key, unique |
| `checksum` | Data | sha256 hex, indexed |
| `file_size` | Int | bytes |
| `mime_type` | Data | sniffed from content, not from filename |
| `driver` | Data | driver name, e.g. `local`, `s3` |
| `is_private` | Check | decides local dir and URL policy |
| `status` | Select | `Pending` (upload in flight) / `Ready` |

- Unique index on `(checksum, is_private, driver)`. This replaces the
  current dedup-by-shared-`file_url` trick with a real entity.
- No `attached_to_*`, no folder, no filename. Those belong to `File`.
- The blob has no refcount column. Reference count = count of `File`
  rows that link to it. Counting at GC time cannot drift.

Key layout is content-addressed:

```python
def make_key(checksum: str) -> str:
    return f"{checksum[:2]}/{checksum[2:4]}/{checksum}"
```

The filename is not part of the key. `Content-Disposition` supplies it
at download time. This fixes the guessable `/files/invoice.pdf` problem
for v2 files.

Public v2 blobs are exposed at their plain nginx path:
`file_url = /files/blobs/ab/cd/<hash>.<ext>`. nginx serves them with no
Python, as today, and the hash makes the URL non-guessable. The `/f/`
route is for private blobs and for named downloads of public ones.
Trade-off: a public URL cannot be revoked without deleting the blob.

### Changes to `File`

- New field `blob` (Link -> File Blob). Set only on v2 rows.
- `file_url` stays, generated, for backward compatibility.
- `attached_to_doctype/name/field` unchanged. The existing permission
  delegation (file permission = permission on the attached doc,
  `file.py:976`) is kept as is. It is the best part of the current
  module.
- N attachments of the same content = N `File` rows, one blob. Today
  this is N rows sharing a `file_url` string with no owner.

### Controller split (decision, added after review)

No flag branches inside the File class. Three files instead:

- `file.py`: storage-agnostic base (fields, folders, permissions,
  naming, 11 storage seams).
- `file_v1.py`: legacy disk behavior, moved verbatim. Deleted when v1
  retires.
- `file_v2.py`: clean blob-native class.

`File.resolve_controller()` picks V1 or V2 from the flag. A 12-line
seam in `import_controller` calls it; the result is cached per site
(one process serves many sites, so import-time switching is not
possible). `override_doctype_class` subclasses still win via MRO
splicing. Cross-version shims keep both directions revertible: V2
reads pre-backfill rows, V1 reads blob rows after a flag rollback.

## Driver interface

```python
# frappe/storage/driver.py
from abc import ABC, abstractmethod
from typing import IO

class StorageDriver(ABC):
	name: str

	@abstractmethod
	def write(self, key: str, stream: IO[bytes]) -> None: ...

	@abstractmethod
	def read(self, key: str) -> IO[bytes]:
		"""Return a readable stream. Never the full bytes."""

	@abstractmethod
	def delete(self, key: str) -> None: ...

	@abstractmethod
	def exists(self, key: str) -> bool: ...

	def download_url(self, key: str, filename: str, expires_in: int) -> str | None:
		"""Native signed URL (e.g. S3 presigned GET).
		None means: the framework serves the bytes itself."""
		return None

	def upload_target(self, key: str, size: int) -> dict | None:
		"""Native direct-upload target (e.g. S3 presigned POST).
		None means: client must use the framework upload endpoint."""
		return None
```

Registration through hooks, selection through site config:

```python
# hooks.py of any app
storage_drivers = {"s3": "myapp.storage.s3.S3Driver"}

# site_config.json
"storage_v2": 1,
"storage_driver": "s3",
"storage_driver_config": {"bucket": "...", "region": "..."}
```

Core ships `local` (default) and `s3` (boto3, optional dependency).
The local driver writes under `private/files/blobs/` and
`public/files/blobs/`.

Rule: **every** byte access goes through the driver. Today
`get_content`, `get_full_path`, thumbnails, `unzip`, and the privacy
move all call `open()` directly, which is why the current `write_file`
hook cannot support a real backend.

## Blob service

```python
# frappe/storage/blob.py
def put_blob(stream: IO[bytes], *, is_private: bool) -> "FileBlob":
	spool = spool_to_tempfile(stream)          # never full bytes in RAM
	checksum = sha256_of(spool)
	mime = sniff_mime(spool)                   # filetype lib, from bytes

	existing = frappe.db.get_value(
		"File Blob",
		{"checksum": checksum, "is_private": is_private, "driver": driver.name},
	)
	if existing:
		return frappe.get_doc("File Blob", existing)   # dedup, no write

	blob = frappe.new_doc("File Blob")
	blob.update({
		"key": make_key(checksum), "checksum": checksum,
		"file_size": spool.size, "mime_type": mime,
		"driver": driver.name, "is_private": is_private,
		"status": "Ready",
	})
	driver.write(blob.key, spool)
	blob.insert()
	return blob
```

Notes:

- sha256 replaces MD5. Old rows keep `content_hash` untouched.
- The blob is immutable. "Optimize image" creates a new blob and
  repoints the `File` row. Today it rewrites bytes in place and
  silently changes the hash under every row that shares the URL.
- On transaction rollback, a `Pending` blob with no `Ready` flip is
  cleaned by GC. No custom rollback hooks on the write path.

## HTTP layer

### Signed URLs

```python
# frappe/storage/url.py
def signed_url(file: "File", expires_in: int = 3600) -> str:
	blob = file.blob_doc
	native = driver.download_url(blob.key, file.file_name, expires_in)
	if native:
		return native                           # e.g. S3 presigned GET

	expires = now_epoch() + expires_in
	payload = f"{blob.name}:{file.file_name}:{expires}"
	sig = hmac_sha256(site_secret(), payload)
	return f"/f/{blob.name}/{quote(file.file_name)}?e={expires}&s={sig}"
```

- A valid signature grants access with **no session and no DB
  permission query**. That is the point: a private file becomes
  shareable, and nginx-level caching becomes possible.
- Session-authenticated access to `/f/...` without a signature still
  works and runs the existing permission delegation.
- Nothing like this exists today. `unique_url`'s `?fid=` is a lookup
  hint, not a token.

### Embedded URLs (rich text, print formats, email)

Stored content always holds a **stable, unsigned URL**. A signed URL is
never stored, because content outlives any TTL. Signing happens at
egress.

- `<img src>` / Attach fields, public blob: the plain nginx path
  (`/files/blobs/...`).
- `<img src>` / Attach fields, private blob: `/f/<blob>/<filename>`
  with no signature. Desk, portal, and web-form rendering authenticate
  it with the session cookie and the existing permission delegation,
  like `/private/files/` today.
- Email send: outgoing HTML is rewritten at send time. Private `/f/`
  URLs become signed URLs with a long TTL (default 30 days, site
  configurable), or are inlined as `cid:` attachments. Today external
  recipients of private images get a login redirect.
- PDF / print render: the renderer requests short-TTL signed URLs at
  render time. This replaces the current special-cased direct disk
  reads in the chromium path.

### Serve route `/f/<blob>/<filename>`

```python
def serve(blob_name, filename):
	verify_signature_or_permission()
	blob = get_blob(blob_name)
	native = driver.download_url(blob.key, filename, 60)
	if native:
		return redirect(native)                 # cloud driver: 302
	if request.headers.get("X-Use-X-Accel-Redirect"):
		return x_accel(blob.local_path)         # local driver: nginx sends bytes
	return send_file(driver.read(blob.key), conditional=True)  # Range support
```

Redirect mode and proxy mode, like Rails. The X-Accel path and the
`conditional=True` Range handling already exist in
`response.py:325-356` and are reused.

### Upload

Three-step flow. Fixes the temp-file collision, the
size-check-after-write gap, and the missing resumability.

```python
# 1. client asks for an upload session
@frappe.whitelist(methods=["POST"])
def create_upload(filename, size, doctype=None, docname=None):
	check_attach_permission(doctype, docname)   # write perm, always
	check_max_file_size(size)                   # before any byte lands
	native = driver.upload_target(temp_key(), size)
	if native:
		return {"mode": "direct", **native}     # browser -> S3, workers untouched
	return {"mode": "chunked", "upload_id": frappe.generate_hash(20)}

# 2. chunked fallback: PUT /api/method/...upload_chunk?upload_id=&offset=
#    temp path is keyed by upload_id, not by client filename.
#    Cumulative size is enforced per chunk. Sessions expire after 24h (GC).

# 3. finish
@frappe.whitelist(methods=["POST"])
def finish_upload(upload_id, checksum, **attach_args):
	blob = put_blob(open_upload(upload_id), is_private=...)
	if checksum and blob.checksum != checksum:
		frappe.throw(_("Checksum mismatch"))
	return create_file_row(blob, **attach_args).as_dict()
```

### Validation

```python
def sniff_mime(stream) -> str:
	kind = filetype.guess(stream.read(8192))
	return kind.mime if kind else "application/octet-stream"

def validate_upload(blob, claimed_filename):
	ext_mime = mimetypes.guess_type(claimed_filename)[0]
	if is_active_content(blob.mime_type) and blob.mime_type != ext_mime:
		frappe.throw(_("File content does not match its extension"))
	check_allowed_types(blob.mime_type)         # allowlist keys on sniffed MIME
```

Today every check (extension allowlist, guest MIME list, PDF-JS scan,
forced-download list) keys on `mimetypes.guess_type(filename)`.
Renaming `evil.html` to `evil.png` defeats all of them. The `filetype`
lib is already a dependency; it is just never cross-checked.

Permission tightening under the flag: `frappe.client.attach_file`
requires **write** permission on the target doc, matching
`upload_file`. Today it only checks read.

## Lifecycle

Daily scheduled job:

```python
def collect_garbage():
	orphans = frappe.db.sql("""
		select b.name, b.key from `tabFile Blob` b
		left join `tabFile` f on f.blob = b.name
		where f.name is null
		  and b.modified < %(cutoff)s
	""", {"cutoff": add_days(now(), -1)}, as_dict=True)
	for b in orphans:
		driver.delete(b.key); frappe.delete_doc("File Blob", b.name)
	expire_stale_upload_sessions()
```

- Deleting a `File` row never touches bytes synchronously. GC does.
  This removes the count-on-`content_hash` delete logic in
  `file.py:608`, including its known public/private stale-file bug.
- Also sweeps `Pending` blobs and dead `.temp` upload sessions. Today
  aborted chunk uploads leave `.temp-*` files forever.

## Tests

```python
with frappe.storage.fake() as store:        # in-memory driver
	file = attach_bytes(b"hello", "a.txt", doc)
	assert store.exists(file.blob_doc.key)
```

`fake()` swaps the driver registry for a `MemoryDriver` and restores it
on exit. No test touches `sites/<site>/public/files`. Modeled on
Laravel's `Storage::fake()`.

## Backfill and compatibility

- Patch (idempotent, batched): group existing `File` rows by
  `(content_hash, is_private)`, create one `File Blob` per group
  pointing at the existing path as its key, link the rows. sha256 is
  computed from disk during backfill; unreadable files are logged and
  skipped, not failed.
- `file_url` keeps working for both generations. `get_full_path` and
  `download_private_file` learn one extra branch: row has `blob` ->
  resolve through the driver.
- The legacy write path (`utils/file_manager.py`) is not ported. Under
  the flag it forwards to `put_blob`. The old `write_file` /
  `delete_file_data_content` hooks are ignored for v2 rows and
  deprecation-warned.

## Rollout stages

1. Driver interface, local driver, `File Blob`, `put_blob`, dual-path
   reads. Flag off by default.
2. Signed URLs and the `/f/` serve route.
3. Upload sessions: direct upload, resumable chunks, sniff validation.
4. GC job, backfill patch, storage fake.
5. S3 driver. Then default-on for new sites.

Each stage is independently shippable and revertible by the flag.

## Decisions (from review)

1. Hashing: sha256 for new blobs, old MD5 rows untouched, backfill
   computes sha256 from disk. Approved.
2. Embedded URLs: stable unsigned URLs in content, signing at egress
   (email send, PDF render). See "Embedded URLs" above. Signed URL
   default TTL 1 hour; email variant 30 days, site configurable.
3. `attach_file` requires write permission under the flag. Approved.
4. Public v2 files: plain nginx URLs at `/files/blobs/<key>`. Zero
   Python per request, non-guessable by hash. No human filename in the
   URL, not revocable without deleting the blob. Named downloads of
   public files can use `/f/`. Matches Laravel's public disk and
   Rails' `public: true` services. Approved.

No open questions. The spec is ready for implementation planning.
