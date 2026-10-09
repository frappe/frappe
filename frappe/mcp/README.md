# Built-in MCP server

Frappe exposes four tools at `/api/mcp` for agents to inspect schemas, read and change documents, and call existing methods.
The endpoint is enabled by default and uses the authenticated site user's permissions.
It supports Streamable HTTP with JSON responses and protocol versions `2025-11-25` and `2026-07-28`.

## Connect to a site

1. As a System Manager, open the agent's **User** document.
2. Select **API Access → Generate Keys**.
3. Copy the API key and secret.

Set these variables before launching your client:

```bash
export FRAPPE_MCP_URL='https://your-site.example.com/api/mcp'
export FRAPPE_MCP_AUTH='token YOUR_API_KEY:YOUR_API_SECRET'
```

For OAuth, set `FRAPPE_MCP_AUTH` to `Bearer YOUR_ACCESS_TOKEN`.
Configure each site with its own URL and credentials.
Regenerating keys replaces the secret. Keep credentials out of version control.

## Client setup

Launch the client from the terminal where you set `FRAPPE_MCP_AUTH`.

### MCP Inspector

With Node.js installed, list the tools:

```bash
npx @modelcontextprotocol/inspector --cli "$FRAPPE_MCP_URL" \
  --transport http --method tools/list \
  --header "Authorization: $FRAPPE_MCP_AUTH"
```

### Codex

Add this entry to `~/.codex/config.toml`:

```toml
[mcp_servers.frappe]
url = "https://your-site.example.com/api/mcp"
env_http_headers = { Authorization = "FRAPPE_MCP_AUTH" }
```

### Claude Code

```bash
claude mcp add-json --scope user frappe \
  '{"type":"http","url":"https://your-site.example.com/api/mcp","headers":{"Authorization":"${FRAPPE_MCP_AUTH}"}}'
```

Run `/mcp` in Claude Code to inspect the connection.

Client references: [Inspector](https://github.com/modelcontextprotocol/inspector/blob/main/clients/cli/README.md), [Codex](https://developers.openai.com/codex/mcp/), [Claude Code](https://code.claude.com/docs/en/mcp).

## Tools

Examples show tool arguments, which the client sends through `tools/call`.

| Tool | Purpose | Example arguments |
| --- | --- | --- |
| `discover` | Inspect site metadata, DocType schemas, and permitted method contracts. | `{"doctype":"ToDo"}` |
| `get_documents` | Read a document, list matches, or count matches. | `{"doctype":"ToDo","filters":{"status":"Open"},"fields":["name","description"],"limit":20}` |
| `write_document` | Create, update, or delete one document. | `{"action":"create","doctype":"ToDo","data":{"description":"Check MCP"}}` |
| `call_method` | Call a whitelisted API or document method. | `{"method":"frappe.auth.get_logged_user"}` |

- `discover`: use no arguments for a site overview, `query` to search, or `doctype` to inspect a schema.
  Use `method` to inspect a method. Do not combine `query` with the other arguments.
- `get_documents` accepts `name` for one document or `count_only: true` for a count.
  Lists default to `start: 0`, `limit: 20`, and the `name` field. Use `has_next_page` to continue paging.
- `write_document` requires `data` for create and update, and `name` for update and delete.
  Submit and cancel use `call_method` with `doctype`, `name`, and `method`.
- `call_method` accepts an `args` object. Add `doctype` for a controller module function and `name` for a stored document method.

### Permissions

Authenticated users can inspect DocType schemas, including those they cannot read.
Document reads and writes still require Frappe permissions.
Method discovery requires System Manager access, but calling a known method does not require that role.
Whitelisted RPC methods remain responsible for their own permission checks.

## Configuration and troubleshooting

To disable the endpoint for one site:

```bash
bench --site your-site.example.com set-config disable_mcp_server 1
```

Set the value to `0` to enable it again.
Restart backend processes after installing Python changes. An asset build is not needed for this endpoint.

| Response | Check |
| --- | --- |
| `405` | Send MCP requests through POST. Opening the URL in a browser sends GET. |
| `404` | Check the site URL, installed code, and `disable_mcp_server`. |
| `401` | Check the credentials and Authorization header. |
| `403` | Check permissions and the site's Origin policy. |
| `406` / `415` | Allow `application/json` in Accept and send `Content-Type: application/json`. |
