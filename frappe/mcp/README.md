# Built-in MCP server

Frappe exposes 14 tools at `/api/v2/mcp` for agents to inspect schemas, read and change documents, and call existing methods.
The endpoint is enabled by default and uses the authenticated site user's permissions.
It supports Streamable HTTP with JSON responses and protocol versions `2025-11-25` and `2026-07-28`.

## Connect to a site

1. As a System Manager, open the agent's **User** document.
2. Select **API Access → Generate Keys**.
3. Copy the API key and secret.

Set these variables before launching your client:

```bash
export FRAPPE_MCP_URL='https://your-site.example.com/api/v2/mcp'
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
url = "https://your-site.example.com/api/v2/mcp"
env_http_headers = { Authorization = "FRAPPE_MCP_AUTH" }
```

### Claude Code

```bash
claude mcp add-json --scope user frappe \
  '{"type":"http","url":"https://your-site.example.com/api/v2/mcp","headers":{"Authorization":"${FRAPPE_MCP_AUTH}"}}'
```

Run `/mcp` in Claude Code to inspect the connection.

Client references: [Inspector](https://github.com/modelcontextprotocol/inspector/blob/main/clients/cli/README.md), [Codex](https://developers.openai.com/codex/mcp/), [Claude Code](https://code.claude.com/docs/en/mcp).

## Tools

Examples show tool arguments, which the client sends through `tools/call`.

| Tool | Purpose | Example arguments |
| --- | --- | --- |
| `search_doctypes` | Find DocTypes by name or module. | `{"query":"ToDo"}` |
| `get_doctype_schema` | Inspect fields and permissions. | `{"doctype":"ToDo"}` |
| `search_methods` | Find whitelisted methods. | `{"query":"get_count"}` |
| `get_method_schema` | Inspect an API function's arguments. | `{"method":"frappe.client.get_count"}` |
| `list_document_methods` | List whitelisted instance methods. | `{"doctype":"ToDo"}` |
| `get_document_method_schema` | Inspect an instance method's arguments. | `{"doctype":"ToDo","method":"add_comment"}` |
| `list_documents` | List matching documents with pagination. | `{"doctype":"ToDo","filters":{"status":"Open"},"fields":["name","description"],"limit":20}` |
| `get_document` | Read one document and its permitted child rows. | `{"doctype":"ToDo","name":"TODO-00001"}` |
| `count_documents` | Count matching documents. | `{"doctype":"ToDo","filters":{"status":"Open"}}` |
| `create_document` | Create one document. | `{"doctype":"ToDo","data":{"description":"Check MCP"}}` |
| `update_document` | Update one document. | `{"doctype":"ToDo","name":"TODO-00001","data":{"status":"Closed"}}` |
| `delete_document` | Delete one document. | `{"doctype":"ToDo","name":"TODO-00001"}` |
| `call_method` | Call a whitelisted API function. | `{"method":"frappe.auth.get_logged_user"}` |
| `call_document_method` | Call a whitelisted instance method on one document. | `{"doctype":"ToDo","name":"TODO-00001","method":"add_comment","args":{"text":"Checked"}}` |

Lists default to `start: 0`, `limit: 20`, and the `name` field. Use `has_next_page` to continue paging.
Method calls accept an `args` object. Controller module functions use their full dotted path with `call_method`.
Submit and cancel use `call_document_method` with `doctype`, `name`, and `method`.
A method whitelisted for GET but not POST runs as an HTTP GET runs it: it needs read permission, and its writes roll back. Every other method runs as POST.

### Permissions

Desk users can inspect DocType schemas and discover methods, including those they cannot read or call.
Document reads and writes still require Frappe permissions.
Whitelisted RPC methods remain responsible for their own permission checks.

## Configuration and troubleshooting

Open **MCP Settings** as a System Manager to set the server name for this site.
When it is empty, the name is the site's host name in lowercase, with each run of other characters changed to `_`.
For example, `erp.example.com` becomes `erp_example_com`.
**Enable MCP** is checked by default. Uncheck it to disable the endpoint for this site.
Clients receive instructions during initialization or server discovery.
They give the site URL, the authenticated user, and the installed apps with their descriptions.
Use **Agent Instructions** for site-specific guidance. Frappe appends it to these instructions.
Instructions do not change permissions.

The existing `disable_mcp_server` site config also forces the endpoint off, regardless of the checkbox.

Restart backend processes after installing Python changes. An asset build is not needed for this endpoint.

| Response | Check |
| --- | --- |
| `405` | Send MCP requests through POST. Opening the URL in a browser sends GET. |
| `404` | Check the site URL, installed code, and `disable_mcp_server`. |
| `401` | Check the credentials and Authorization header. |
| `403` | Check that the user is a System User, then check permissions and the site's Origin policy. |
| `406` / `415` | Allow `application/json` in Accept and send `Content-Type: application/json`. |
