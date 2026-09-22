# Server calls go through one wrapper on `/api/v2`

Every request a screen in `ui/src` or the desk sends goes through `@framework/ui/api`.
The wrapper sends to `/api/v2` only. Screens never import frappe-ui's fetch primitives
(`call`, `createResource*`, `useCall`, `useList`, `useDoc`, `useNewDoc`, `useDoctype`,
`useFileUpload`). The callers written before it move onto the wrapper region by region
on the API v2 map; until then both exist side by side.

## Why the wrapper owns its transport

frappe-ui has no stable 1.0.0. Its old toolkit sends to `/api/method` and reads
`message`; its new toolkit sends to `/api/v2` but hands a caller `data` alone, and its
author has said a third toolkit will replace it. The desk needs the keys the server
writes **beside** `data`: `has_next_page` on a list, and the named `include` parts on a
document read. `useCall` hides them and the fetch instance under it is not exported, so
the wrapper calls `fetch` itself, with the same headers frappe-ui sends. A change of
transport later touches this folder only.

## The rules the wrapper enforces

- **Every function returns the envelope.** `const { data, has_next_page } = await
  listDocuments(...)`. What the server returned is what the caller gets; nothing is
  reshaped on the way.
- **A save always sends `modified`.** `updateDocument` refuses a document without it,
  before any request. That is what keeps the server's `TimestampMismatchError`, which the
  caller reads from `error.type`.
- **`include` and `or_filters` are pass-throughs.** The server grows `include` on the
  document read and on meta, and `or_filters` on the list, in the record region's PR; the
  wrapper already sends them.
- **`filters` and `or_filters` are opaque.** The wrapper JSON-encodes what it is given and
  models no grammar; a new server grammar changes no call site.
- **One error class.** The first entry of the server's `errors` list becomes an
  `ApiError` with `type`, `title`, `exception`, `indicator` and the HTTP status. A
  failed response with no JSON body is an `HTTPError`, and a 200 whose body has no `data`
  is a `MissingData`, since the server writes `data` only when the endpoint returned a
  value. A caller of `runMethod` or `runDocumentMethod` whose function returns nothing
  says `nullable`, and `data` is then `null`; `logout` and a non-final upload part are
  nullable inside the wrapper.

## The surface

`getDocument`, `listDocuments`, `countDocuments`, `createDocument`, `updateDocument`,
`deleteDocument`, `copyDocument`, `runMethod`, `runDocumentMethod`, `getMeta`, the file
calls `uploadFile`, `attachFile`, `removeAttachment` and `downloadFile`, and the pieces a
caller needs to build a request of its own: `apiUrl`, `requestHeaders` and `readEnvelope`.
A dotted method under `runMethod` is a first-class route, not a fallback; which v1
functions move there is decided per region on the API v2 map.
