// HTTP + SSE client for the flow daemon. fetch-based (not EventSource) so the
// Authorization header works. This is the only module that talks to the network;
// Flow's Frappe shell can swap it for a proxy-backed implementation with the
// same surface.

const enc = encodeURIComponent

export class FlowAPIError extends Error {
	constructor(status, message, data = null) {
		super(message)
		this.status = status
		this.data = data
	}
}

async function raise(response) {
	let detail = `${response.status} ${response.statusText}`
	let data = null
	try {
		data = await response.json()
		if (typeof data.detail === "string") detail = data.detail
		else if (data.detail) detail = JSON.stringify(data.detail)
	} catch {
		// non-JSON error body
	}
	// this UI never sends a wrong method to its own daemon — a 405 (or the
	// router's generic unknown-route 404, distinct from any endpoint's own
	// detail) means the daemon process predates the served bundle
	if (response.status === 405 || (response.status === 404 && detail === "Not Found")) {
		detail = "The daemon is running older code than this UI — restart it and retry."
	}
	throw new FlowAPIError(response.status, detail, data)
}

export class DaemonClient {
	constructor({ baseUrl = "", token = "" } = {}) {
		this.baseUrl = baseUrl.replace(/\/+$/, "")
		this.token = token
	}

	headers(extra = {}) {
		const h = { ...extra }
		if (this.token) h["Authorization"] = `Bearer ${this.token}`
		return h
	}

	async request(method, path, { body, params } = {}) {
		const url = new URL(this.baseUrl + path, window.location.origin)
		for (const [k, v] of Object.entries(params ?? {})) url.searchParams.set(k, v)
		const response = await fetch(url, {
			method,
			headers: this.headers(body !== undefined ? { "Content-Type": "application/json" } : {}),
			body: body !== undefined ? JSON.stringify(body) : undefined,
		})
		if (!response.ok) await raise(response)
		return response.json()
	}

	health() {
		return this.request("GET", "/healthz")
	}
	models() {
		return this.request("GET", "/models")
	}
	sessions() {
		return this.request("GET", "/sessions")
	}
	session(sid) {
		return this.request("GET", `/sessions/${enc(sid)}`)
	}
	skills(sid) {
		return this.request("GET", `/sessions/${enc(sid)}/skills`)
	}
	previewSkills(config = {}) {
		return this.request("POST", "/skills", { body: config })
	}
	// built-in and extension tools a session may enable under the daemon's policy
	tools() {
		return this.request("GET", "/tools")
	}
	// the web UI's settings, kept by the daemon; a save merges the keys it sends
	settings() {
		return this.request("GET", "/settings")
	}
	updateSettings(settings) {
		return this.request("PATCH", "/settings", { body: { settings } })
	}
	// the sidebar's workspaces, kept by the daemon: named folders it groups chats under
	workspaces() {
		return this.request("GET", "/workspaces")
	}
	addWorkspace(path) {
		return this.request("POST", "/workspaces", { body: { path } })
	}
	renameWorkspace(path, name) {
		return this.request("PATCH", "/workspaces", { body: { path, name } })
	}
	removeWorkspace(path) {
		return this.request("DELETE", "/workspaces", { params: { path } })
	}
	// skill files under the global root and, with a cwd, the project's
	skillFiles(cwd = null) {
		return this.request("GET", "/skills", { params: cwd ? { cwd } : {} })
	}
	readSkill(path, cwd = null) {
		return this.request("GET", "/skills/file", { params: cwd ? { path, cwd } : { path } })
	}
	writeSkill(path, content, cwd = null) {
		return this.request("PUT", "/skills/file", { body: { path, content, cwd } })
	}
	deleteSkill(path, cwd = null) {
		return this.request("DELETE", "/skills/file", { params: cwd ? { path, cwd } : { path } })
	}
	// the session's active branch — replay-safe seed for a fresh transcript
	entries(sid) {
		return this.request("GET", `/sessions/${enc(sid)}/entries`)
	}
	// the explorer calls, keyed by the browsed cwd: one directory level, a
	// file-name search, and a file's text content
	listFiles(cwd, path = "") {
		return this.request("GET", "/fs/files", { params: { cwd, path } })
	}
	searchFiles(cwd, query) {
		return this.request("GET", "/fs/files/search", { params: { cwd, query } })
	}
	readFile(cwd, path) {
		return this.request("GET", "/fs/file", { params: { cwd, path } })
	}
	writeFsFile(cwd, path, content) {
		return this.request("PUT", "/fs/file", { body: { cwd, path, content } })
	}
	// the repository's uncommitted files, and one file's HEAD + working-tree
	// content for the diff viewer — cwd-keyed like the other explorer calls
	gitChanges(cwd) {
		return this.request("GET", "/fs/git/changes", { params: { cwd } })
	}
	gitBranch(cwd) {
		return this.request("GET", "/fs/git/branch", { params: { cwd } })
	}
	gitFileDiff(cwd, path) {
		return this.request("GET", "/fs/git/file/diff", { params: { cwd, path } })
	}
	// session-recorded original + current content: the diff fallback for files
	// the session changed outside the project repository
	fileDiff(sid, path) {
		return this.request("GET", `/sessions/${enc(sid)}/file/diff`, { params: { path } })
	}
	createSession(config) {
		return this.request("POST", "/sessions", { body: config })
	}
	run(sid, message, attachments = []) {
		return this.request("POST", `/sessions/${enc(sid)}/run`, {
			body: { message, attachments },
		})
	}
	attachFiles(sid, paths) {
		return this.request("POST", `/sessions/${enc(sid)}/attachments/files`, { body: { paths } })
	}
	async uploadAttachments(sid, files) {
		const form = new FormData()
		for (const file of files) form.append("files", file, file.name)
		const url = new URL(this.baseUrl + `/sessions/${enc(sid)}/attachments`, window.location.origin)
		const response = await fetch(url, {
			method: "POST",
			headers: this.headers(),
			body: form,
		})
		if (!response.ok) await raise(response)
		return response.json()
	}
	async attachmentBlob(sid, attachmentId) {
		const url = new URL(
			this.baseUrl + `/sessions/${enc(sid)}/attachments/${enc(attachmentId)}`,
			window.location.origin,
		)
		const response = await fetch(url, { headers: this.headers() })
		if (!response.ok) await raise(response)
		return response.blob()
	}
	cleanupAttachments(sid, attachments) {
		return this.request("DELETE", `/sessions/${enc(sid)}/attachments`, {
			body: { attachments },
		})
	}
	resume(sid, approvalSeq, answers) {
		return this.request("POST", `/sessions/${enc(sid)}/resume`, {
			body: { approval_seq: approvalSeq, answers },
		})
	}
	abort(sid) {
		return this.request("POST", `/sessions/${enc(sid)}/abort`)
	}
	cancelPending(sid) {
		return this.request("POST", `/sessions/${enc(sid)}/cancel_pending`)
	}
	rewind(sid, targetSeq) {
		return this.request("POST", `/sessions/${enc(sid)}/rewind`, { body: { target_seq: targetSeq } })
	}
	patchConfig(sid, patch) {
		return this.request("PATCH", `/sessions/${enc(sid)}/config`, { body: patch })
	}
	setModel(sid, { model, credential_id = null, reasoning_effort = null }) {
		return this.request("POST", `/sessions/${enc(sid)}/model`, {
			body: { model, credential_id, reasoning_effort },
		})
	}
	compact(sid, instructions = null) {
		return this.request("POST", `/sessions/${enc(sid)}/compact`, {
			body: instructions ? { instructions } : {},
		})
	}
	deleteSession(sid) {
		return this.request("DELETE", `/sessions/${enc(sid)}`)
	}
	reloadExtensions() {
		return this.request("POST", "/extensions/reload")
	}
	providers() {
		return this.request("GET", "/providers")
	}
	saveCustomProvider(config) {
		return this.request("POST", "/providers/custom", { body: config })
	}
	updateCustomProvider(providerId, config) {
		return this.request("PUT", `/providers/custom/${enc(providerId)}`, { body: config })
	}
	saveProviderKey(providerId, key) {
		return this.request("POST", `/providers/${enc(providerId)}/api-key`, { body: { key } })
	}
	deleteProvider(providerId) {
		return this.request("DELETE", `/providers/${enc(providerId)}`)
	}
	oauthStart(providerId) {
		return this.request("POST", `/providers/${enc(providerId)}/oauth/start`)
	}
	oauthStatus(providerId) {
		return this.request("GET", `/providers/${enc(providerId)}/oauth/status`)
	}
	oauthComplete(providerId, callbackUrl) {
		return this.request("POST", `/providers/${enc(providerId)}/oauth/complete`, {
			body: { callback_url: callbackUrl },
		})
	}
	fsPick() {
		return this.request("POST", "/fs/pick")
	}

	stream(sid, since = 0) {
		return new EventStream(this, sid, since)
	}
}

async function* parseSSE(response) {
	const reader = response.body.getReader()
	const decoder = new TextDecoder()
	let buffer = ""
	try {
		for (;;) {
			const { done, value } = await reader.read()
			if (done) break
			buffer += decoder.decode(value, { stream: true })
			let boundary
			while ((boundary = buffer.indexOf("\n\n")) !== -1) {
				const chunk = buffer.slice(0, boundary)
				buffer = buffer.slice(boundary + 2)
				const data = chunk
					.split("\n")
					.filter((line) => line.startsWith("data:"))
					.map((line) => line.slice(5).trim())
					.join("\n")
				if (data) yield JSON.parse(data)
			}
		}
	} finally {
		reader.cancel().catch(() => {})
	}
}

// Follow-mode event stream with reconnect. Durable events carry `seq`; the
// cursor advances on those and drops replayed duplicates, so a reconnect is
// gapless and duplicate-free. Live-only events (deltas) have no seq and pass
// straight through.
export class EventStream {
	constructor(client, sid, since = 0) {
		this.client = client
		this.sid = sid
		this.cursor = since
		this.closed = false
		this._controller = null
	}

	close() {
		this.closed = true
		this._controller?.abort()
	}

	async *[Symbol.asyncIterator]() {
		let backoff = 500
		while (!this.closed) {
			this._controller = new AbortController()
			try {
				const url = new URL(this.client.baseUrl + `/sessions/${this.sid}/stream`, window.location.origin)
				url.searchParams.set("since", String(this.cursor))
				url.searchParams.set("follow", "true")
				const response = await fetch(url, {
					headers: this.client.headers({ Accept: "text/event-stream" }),
					signal: this._controller.signal,
				})
				if (!response.ok) await raise(response)
				for await (const event of parseSSE(response)) {
					if (typeof event.seq === "number") {
						if (event.seq <= this.cursor) continue
						this.cursor = event.seq
					}
					backoff = 500
					yield event
				}
				// In follow mode the server never closes on purpose; treat a clean
				// close as a drop and reconnect.
			} catch (error) {
				if (this.closed) return
				// only terminal statuses end the stream; a 502/503 from a restarting
				// daemon or proxy is exactly what the reconnect loop is for
				if (error instanceof FlowAPIError && [401, 403, 404].includes(error.status)) {
					throw error
				}
			}
			if (this.closed) return
			await new Promise((resolve) => setTimeout(resolve, backoff))
			backoff = Math.min(backoff * 2, 10_000)
		}
	}
}
