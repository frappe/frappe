# File Storage v2 for Frappe Framework

Design reference for `frappe/storage/`. "Today" means storage v1, the
behavior with the flag off.

> **Status: alpha.** Storage v2 is experimental. Its design will change as
> Suite uses it, and it may be removed. Don't build on its APIs, URLs or
> tables outside Suite yet.

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
| `key` | Data | driver-scoped object key, indexed |
| `checksum` | Data | sha256 hex, indexed |
| `file_size` | Int, `length: 20` | bytes; a bigint, so a 5 TB object fits |
| `mime_type` | Data | sniffed from content, not from filename |
| `driver` | Data | driver name, e.g. `local`, `s3` |
| `is_private` | Check | decides local dir and URL policy |
| `status` | Select | `Pending` / `Ready`; `put_blob` writes `Ready` |

- No unique index on content. Dedup is a best-effort lookup on the
  `checksum` index, scoped by `is_private` and `driver`. Duplicate blobs
  are accepted: two concurrent identical uploads may each get a blob,
  backfill gives each legacy path its own blob, and relocation may move
  a blob to a driver that already holds the same content.
- No `attached_to_*`, no folder, no filename. Those belong to `File`.
- The blob has no refcount column. Reference count = count of `File`
  rows that link to it. Counting at GC time cannot drift.

Key layout is the blob name and the first upload's filename:

```python
def make_key(driver, blob_name: str, filename: str) -> str:
    return f"{driver.key_prefix}{blob_name}/{key_filename(filename)}"
```

`put_blob` names the blob before writing, so the key is known up front.
Dedup finds identical content through the `checksum` index, not the key.
A deduplicated upload gets the existing blob, and with it the first
upload's filename in its URL.

URLs keep v1's prefixes, and with them v1's meaning: `/files/` is public
and `/private/files/` is private.

| Blob | `file_url` | Served by |
|---|---|---|
| Public, local | `/files/<blob>/<filename>` | nginx, from `public/files/<blob>/<filename>` |
| Public, other driver | `/files/<blob>/<filename>` | Python: redirect to the driver's URL |
| Private | `/private/files/<blob>/<filename>` | Python: permission check, then X-Accel or redirect |
| Backfilled v1 file | unchanged `/files/x`, `/private/files/x` | disk, or the blob once relocated |

A public local blob sits on disk at its URL path, so nginx serves it with
no Python and no config change. The random 10-character blob name keeps
the URL hard to guess, which fixes the guessable `/files/invoice.pdf`
problem for v2 files. A v1 URL is flat (`/files/logo.png`); a blob URL
always has two parts, the first a blob name, so the two cannot collide.
Trade-off: a public URL cannot be revoked without deleting the blob, and
a privacy change gives the file a new URL, as in v1.

### Changes to `File`

- New field `blob` (Link -> File Blob). Set only on v2 rows.
- `file_url` stays, generated, for backward compatibility.
- `attached_to_doctype/name/field` unchanged. The existing permission
  delegation (file permission = permission on the attached doc,
  `has_permission` in `file.py`) is kept as is. It is the best part
  of the current module.
- N attachments of the same content = N `File` rows, one blob. Today
  this is N rows sharing a `file_url` string with no owner.

### Controller split (decision, added after review)

No flag branches inside the File class. Three files instead:

- `file.py`: storage-agnostic base (fields, folders, permissions,
  naming, 11 storage seams).
- `file_v1.py`: legacy disk behavior, moved verbatim. Deleted when v1
  retires.
- `file_v2.py`: clean blob-native class.

`File.resolve_controller()` picks V1 or V2 from the flag.
`import_controller` calls it through `_resolve_controller`; the result
is cached per site (one process serves many sites, so import-time
switching is not possible). `override_doctype_class` subclasses still win via MRO
splicing. Cross-version shims keep both directions revertible: V2
reads pre-backfill rows, V1 reads blob rows after a flag rollback.

## Driver interface

```python
# frappe/storage/driver.py
from abc import ABC, abstractmethod
from typing import IO

class StorageDriver(ABC):
	name: str
	key_prefix: str = ""    # prepended to every new key

	@abstractmethod
	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None: ...

	@abstractmethod
	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		"""Return a readable binary stream. Never the full bytes."""

	@abstractmethod
	def delete(self, key: str, *, is_private: bool = False) -> None: ...

	@abstractmethod
	def exists(self, key: str, *, is_private: bool = False) -> bool: ...

	def read_range(self, key, start, end, *, is_private=False) -> IO[bytes]:
		"""Bytes start..end inclusive. The default reads the whole object."""

	def download_url(self, key, filename, expires_in, *, is_private=False,
			mime_type=None, as_attachment=False) -> str | None:
		"""Native signed URL (e.g. S3 presigned GET).
		None means: the framework serves the bytes itself."""
		return None

	def upload_target(self, key, size, *, is_private=False) -> dict | None:
		"""Native direct-upload target (e.g. S3 presigned POST).
		None means: the client sends chunks through the upload session."""
		return None
```

Keys carry no privacy, so every method takes `is_private` to pick the
public or private namespace. A driver that returns a `download_url` must
serve the type and disposition that `blob.served_type` gives.

Registration through hooks, selection through site config:

```python
# hooks.py of any app
storage_drivers = {"s3": "myapp.storage.s3.S3Driver"}

# site_config.json
"storage_v2": 1,
"storage_driver": "s3",
"storage_driver_config": {"bucket": "...", "region": "..."}
```

Core ships `local` (default), `s3` (boto3, optional dependency) and
`memory` (tests). The local driver writes under `private/files/` and
`public/files/`. The S3 object key is `public/` or `private/` followed by
the blob key.

Site prefix: a driver shared by several sites, such as one S3 bucket,
starts every new key with the site's folder. For S3 it is
`storage_driver_config.prefix`, or by default 12 hex characters of the
SHA-256 of the database name (set once, unique on a server, and not shown
in presigned URLs). The prefix is stored in each key, not added at read
time, and the driver deletes only keys under the current prefix. A
staging site restored from production can still read production's
objects, but its garbage collection never deletes them.

Rule: **every** byte access goes through the driver. Today
`get_content`, `get_full_path`, thumbnails, `unzip`, and the privacy
move all call `open()` directly, which is why the current `write_file`
hook cannot support a real backend.

## Blob service

```python
# frappe/storage/blob.py
def put_blob(stream, *, is_private=False, filename=None) -> "FileBlob":
	driver = get_driver()
	spool, size = spool_to_tempfile(stream)    # never full bytes in RAM
	checksum = sha256_of(spool)
	mime_type = sniff_mime(spool)              # filetype lib, from bytes

	existing = frappe.db.get_value(
		"File Blob",
		{"checksum": checksum, "is_private": is_private, "driver": driver.name},
	)
	if existing and revive_blob(existing):     # lock it, bump modified
		return frappe.get_doc("File Blob", existing)   # dedup, no write

	blob = frappe.new_doc("File Blob")
	blob.set_new_name()
	blob.update({
		"key": make_key(driver, blob.name, filename), "checksum": checksum,
		"file_size": size, "mime_type": mime_type,
		"driver": driver.name, "is_private": is_private,
		"status": "Ready",
	})
	frappe.db.after_rollback.add(delete_bytes_on_rollback(driver, blob.key, is_private))
	driver.write(blob.key, spool, is_private=is_private)
	blob.insert()
	return blob
```

Notes:

- sha256 replaces MD5. Old rows keep `content_hash` untouched.
- The blob is immutable. "Optimize image" creates a new blob and
  repoints the `File` row. Today it rewrites bytes in place and
  silently changes the hash under every row that shares the URL.
- On transaction rollback, the `File Blob` row rolls back and an
  `after_rollback` callback deletes the bytes `put_blob` wrote.
- `revive_blob` locks a reused blob and bumps its `modified`, so GC
  keeps it until the new link commits. Dedup, `File.revive_linked_blob`
  (a row linked to an existing blob) and v1's `share_stored_file` all
  call it.

## HTTP layer

### Signed URLs

```python
# frappe/storage/url.py
def signed_url_for_blob(blob, filename, expires_in=3600, *, as_attachment=False) -> str:
	native = driver.download_url(blob.key, filename, expires_in, ...)
	if native:
		return native                           # e.g. S3 presigned GET

	expires = int(time.time()) + expires_in
	payload = f"{blob.name}:{filename}:{expires}"
	sig = hmac_sha256(get_signing_key(), payload)   # derived from encryption_key
	return f"{prefix}{blob.name}/{quote(filename)}?e={expires}&s={sig}"
```

`signed_url(file, expires_in)` calls it with the File's blob and
`file_name`. `prefix` follows the blob's privacy. `&download=1` makes the
file download instead of showing inline.

- A valid signature grants access with **no session and no DB
  permission query**. That is the point: a private file becomes
  shareable, and nginx-level caching becomes possible.
- Session-authenticated access to `/private/files/<blob>/...` without a
  signature still works and runs the existing permission delegation.
- Nothing like this exists today. `unique_url`'s `?fid=` is a lookup
  hint, not a token.

### Embedded URLs (rich text, print formats, email)

Stored content always holds a **stable, unsigned URL**. A signed URL is
never stored, because content outlives any TTL.

- `<img src>` / Attach fields, public blob: `/files/<blob>/<filename>`.
- `<img src>` / Attach fields, private blob:
  `/private/files/<blob>/<filename>` with no signature. Desk, portal, and
  web-form rendering authenticate it with the session cookie and the
  existing permission delegation, like v1 private files.
- Email send: unchanged from v1. A private URL in an email needs a
  login to open. Signed links are an explicit API (`signed_url`), not
  something email adds.
- PDF / print render: the chromium renderer intercepts `/files/` and
  `/private/files/` requests. It reads a file it finds on local disk, as
  in v1. Otherwise it resolves the URL to its blob, including a relocated
  v1 URL, and reads the bytes through the driver
  (`frappe/utils/chromium/page.py`). A private file needs the same
  session permission as the serve route; signatures play no part.

### Serving `/files/` and `/private/files/`

nginx serves any file it finds on disk and passes the rest to Python
(`try_files ... @webserver`). Python then handles:

- `/files/<blob>/<filename>`: a public blob on another driver. No check;
  a 302 to the driver's URL, cacheable for half the URL's lifetime.
- `/private/files/<blob>/<filename>`: a private blob. A valid signature
  or session permission, then a redirect or the bytes.
- Any other path is a v1 URL. A File row with that `file_url` and a blob
  is served from the blob. This keeps v1 URLs working after relocation
  moves their bytes, so stored content never needs rewriting.

`frappe/storage/serve.py` answers an authorized blob in this order: a
302 to the driver's native URL (60 s TTL when private), X-Accel-Redirect
when nginx asks for it, then `send_file` or a ranged driver stream. The
filename in the URL is the download name. Redirect mode and proxy mode,
like Rails. The X-Accel and Range handling mirror `send_private_file` in
`response.py`.

`stream_blob(blob, filename, *, as_attachment=False, environ=None,
allow_native_redirect=False)` serves a blob the caller has already
authorized, with no permission check or access log. It streams by
default, because some clients (WebDAV) cannot follow a cross-host
redirect; pass `allow_native_redirect=True` to allow the 302.

### Upload

`frappe/storage/upload.py` holds upload sessions. It is a trusted
Python API for server code that authorizes the destination itself, such
as Drive. Nothing in it is whitelisted. Fixes the temp-file collision,
the size-check-after-write gap, and the missing resumability.

```python
# 1. open: size check before any byte lands; the session is bound to its owner
create_blob_upload(filename, size, *, is_private=True)
# -> {"mode": "direct", "upload_id", **driver.upload_target(...)}  browser -> bucket
# -> {"mode": "chunked", "upload_id"}

# 2. chunked mode: write at an offset; a retried chunk is fine, a hole is not.
#    Cumulative size is enforced per chunk; an oversize write drops the session.
upload_blob_chunk(upload_id, offset, data)

# 3. finish: claim the session (one winner), put_blob, size and checksum
#    checks, validate_upload. Creates no File row.
finish_upload_to_blob(upload_id, *, checksum=None) -> FileBlob
```

Sessions live in `sites/<site>/private/files/.uploads/` as
`<upload_id>.meta` (json) and `<upload_id>.part`, keyed by
`upload_id`, not by client filename. A direct upload lands at
`upload_key(upload_id)` and is deleted once its blob is stored. The
caller exposes its own HTTP route; a route that reads a raw chunk body
lists itself in the `streaming_request_paths` hook, so `init_request`
does not buffer it. Paths match as written, so list every API mount.

### Validation

```python
def sniff_mime(stream) -> str:
	kind = filetype.guess(stream.read(8192))
	return kind.mime if kind else "application/octet-stream"

def validate_upload(blob, claimed_filename):
	ext_mime = mimetypes.guess_type(claimed_filename)[0]
	if blob.mime_type in ACTIVE_CONTENT_MIME_TYPES and blob.mime_type != ext_mime:
		frappe.throw(_("File content does not match its extension"))
	if blob.mime_type == "application/pdf":
		validate_pdf_content(blob)              # embedded JavaScript
```

`sniff_mime` also detects SVG and HTML text that `filetype` misses.
`served_type` decides the served Content-Type and whether a file must
download, from the sniffed type and the extension.

Today every check (extension allowlist, guest MIME list, PDF-JS scan,
forced-download list) keys on `mimetypes.guess_type(filename)`.
Renaming `evil.html` to `evil.png` defeats all of them. The `filetype`
lib is already a dependency; it is just never cross-checked.

`frappe.client.attach_file` already requires **write** permission on
the target doc, matching `upload_file`.

## Lifecycle

Daily scheduled job:

`frappe.storage.gc.collect_garbage` deletes a blob when no Link field
to `File Blob`, in any doctype, references it and its `modified` is
more than 24 hours old. It re-checks each blob under a row lock before
deleting the bytes, then the row. Then it calls
`expire_stale_upload_sessions`.

- Deleting a `File` row never touches bytes synchronously. GC does.
  This removes, for v2 rows, the count-on-`content_hash` delete logic
  in `FileV1._delete_file_on_disk`, including its known public/private
  stale-file bug.
- Also sweeps upload sessions untouched for 24 hours. Today aborted
  chunk uploads leave `.temp-*` files forever.

## Tests

```python
with frappe.storage.fake() as store:        # in-memory driver
	blob = put_blob(io.BytesIO(b"hello"), is_private=True)
	assert store.exists(blob.key, is_private=True)
```

`fake()` swaps the driver registry for a `MemoryDriver` and restores it
on exit. No test touches `sites/<site>/public/files`. Modeled on
Laravel's `Storage::fake()`.

## Backfill and compatibility

- Backfill (`frappe.storage.backfill.run`, idempotent, batched): group
  legacy `File` rows by `(path, is_private)`, create one `local`
  `File Blob` per group with the existing path as its key, link the
  rows. Backfill does not dedup: two paths with identical bytes get two
  blobs, so each disk file has one owner that GC or relocation can free.
  sha256 is computed from disk; unreadable files are logged and
  skipped, not failed. The `backfill_file_blobs` patch runs it only when
  the flag is on.
- `file_url` keeps working for both generations. `download_private_file`
  and `serve_public_file` serve a v1 URL from its blob when the row has
  one, so `frappe.storage.relocate.relocate_blobs` can move the bytes to
  another driver without changing `file_url`.
- The legacy write path (`utils/file_manager.py`) is not ported. Under
  the flag it forwards to `put_blob`. The old `write_file` /
  `delete_file_data_content` hooks are ignored for v2 rows and
  deprecation-warned.

## Rollout stages

1. Driver interface, local driver, `File Blob`, `put_blob`, dual-path
   reads. Flag off by default.
2. Signed URLs and the blob serve routes.
3. Upload sessions: direct upload, resumable chunks, sniff validation.
4. GC job, backfill patch, storage fake.
5. S3 driver. Then default-on for new sites.

Each stage is independently shippable and revertible by the flag.

## Decisions (from review)

1. Hashing: sha256 for new blobs, old MD5 rows untouched, backfill
   computes sha256 from disk. Approved.
2. Embedded URLs: stable unsigned URLs in content. Email does not sign
   them; PDF render reads the bytes through the driver. See "Embedded
   URLs" above. Signed URL default TTL 1 hour.
3. `attach_file` requires write permission. It already does.
4. URLs reuse v1's prefixes: `/files/<blob>/<filename>` and
   `/private/files/<blob>/<filename>`. No new URL prefix, and code that
   reads privacy from the prefix stays correct. Public local files are
   on disk at their URL path, so nginx serves them with zero Python.
   Not revocable without deleting the blob. Approved.
5. Site prefix: stored in each key, defaulting to a hash of the database
   name; deletes only under the site's own prefix. Approved.

No open questions.
