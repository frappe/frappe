# MCP server

Every Frappe site serves an MCP endpoint at `POST /api/mcp`. An agent points its
MCP client at the site, authenticates with the OAuth flow the site already
supports, and gets a small tool surface over the same semantics as the REST API
v2.

```sh
claude mcp add --transport http frappe https://<site>/api/mcp
```

## Protocol

The server speaks two revisions and lets the client choose. They differ in how
a client announces the protocol version:

| Revision     | Version announced by                                              |
| ------------ | ----------------------------------------------------------------- |
| `2026-07-28` | Every request, in transport headers and `params._meta`.           |
| `2025-11-25` | Once, through the `initialize` handshake.                         |

The newer revision has no handshake and no protocol level session, which makes
the endpoint a plain request/response HTTP workload: no session store, no
session affinity, no long-lived stream. Its transport headers let a proxy route
and a gateway authorize a call without parsing the body, so the server requires
them to agree with the body they describe.

The older revision is what shipping clients speak today. A client on that
revision cannot send the version header on its first request, because it does
not yet know what the server supports, so the header is optional and the
handshake carries the version instead.

| Area          | Support                                                                        |
| ------------- | ------------------------------------------------------------------------------ |
| Endpoint      | `POST /api/mcp`. `GET` and `DELETE` return `405`.                              |
| Response body | Always `application/json`. No SSE.                                             |
| Capabilities  | `tools` only.                                                                  |
| RPC methods   | `initialize`, `ping`, `server/discover`, `tools/list`, `tools/call`            |
| Authorization | The site's OAuth 2.1 resource-server support, or a session.                    |

Omitting SSE is legal: a server chooses per request whether to answer with a
single JSON object or a stream. `subscriptions/listen` and MRTR are
capability-gated, so omitting those is legal too.

A request whose version header names a revision the server does not have gets
`-32022` with the list it does have. An `initialize` asking for an unknown
version gets the newest revision the server has, and the client decides whether
it can continue.

## Tools

Four tools, folded broad. Every tool in the list costs context in the model's
prompt on every turn.

| Tool             | Covers                                                                  |
| ---------------- | ----------------------------------------------------------------------- |
| `discover`       | Site summary, search, DocType schema, and the contract of one method.   |
| `get_documents`  | Read one document, list documents, or count them.                       |
| `write_document` | Create, update and delete.                                              |
| `call_method`    | Every whitelisted method. The escape hatch.                             |

`call_method` is why the tool list stays short. Reports, read-only SQL, file
upload, the submit and cancel lifecycle actions and every app specific method
all go through it.

## Permissions

The MCP layer adds no permission model of its own. Every tool runs as the
authenticated user and relies on Frappe permissions, method whitelisting and
OAuth scopes. An unauthenticated request gets `401` with the `WWW-Authenticate`
challenge the rest of the site sends.

A tool that fails answers with `isError: true` and the message as text, so the
model can read what went wrong and correct itself. The call runs inside a
savepoint, so a failed call leaves no partial write behind.

## Operating

The endpoint is on by default. It requires authentication, and it exposes
nothing that an authenticated REST client cannot already reach. To turn it off,
set `disable_mcp_server` in `site_config.json`; the endpoint then returns `404`.

For an MCP client to complete the authorization flow, the site must publish
OAuth resource metadata. Enable `show_protected_resource_metadata` in **OAuth
Settings**.

Each call reports `mcp_tool=<name>` to the monitor, so MCP traffic is visible
alongside REST traffic.
