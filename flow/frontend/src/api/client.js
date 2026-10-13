import { presentEvent } from "./events.js";
import { SessionStream } from "./stream.js";

const IMAGE_FILE = /\.(png|jpe?g|gif|webp|bmp)$/i;
const SESSION_PAGE = 100; // flow.api.LIST_LIMIT: a shorter page would never read as more

// The store's client surface over flow.api. Sessions are Flow Session docs, models are
// Flow Model docs (the daemon's provider ids are mapped back to them), attachments are
// private Files staged through attach_file. `transport` is the page's Frappe transport
// (frappe.js); `hooks` let the page choose the agent a new chat starts with and mirror
// what the server reports about a session's runs and log.
export class FrappeClient {
	constructor({ socket, boot, transport, hooks = {} }) {
		this.socket = socket;
		this.hooks = hooks;
		this.transport = transport;
		this.configs = new Map(); // session → the config the store last saw
		this.fileIds = new Map(); // file name → the File it was staged as, for this page
		this.boot = boot ?? null; // the page's own boot answers the first models() call
		this.setModels(boot?.models ?? []);
	}

	setModels(models) {
		this.modelRows = models;
		this.modelByProviderId = new Map(models.map((m) => [m.model_id, m.name]));
		this.contextWindows = new Map(models.map((m) => [m.name, m.context_window || null]));
	}

	present(event, sid = event.session_id) {
		return presentEvent(event, {
			fileId: (name, fallback) => this.fileIds.get(name) ?? fallback ?? `file:${name}`,
			modelName: (id) => {
				const selected = this.configs.get(sid)?.model;
				const model = this.modelRows.find((row) => row.name === selected);
				return model?.model_id === id ? selected : this.modelByProviderId.get(id) ?? id;
			},
		});
	}

	// --- catalog ---------------------------------------------------------------

	async models() {
		const boot = this.boot ?? (await this.transport.call("flow.api.boot"));
		this.boot = null;
		this.setModels(boot.models);
		this.hooks.onBoot?.(boot);
		return {
			models: boot.models.map((m) => ({
				name: m.name,
				provider: m.provider || m.model_id.split("/")[0],
				model_id: m.model_id,
				context_window: m.context_window || null,
			})),
			errors: [],
		};
	}

	async tools() {
		return { tools: [] };
	}

	// --- sessions --------------------------------------------------------------

	// One page, newest first; `before` (the last row's modified) continues past it and
	// `query` narrows by title. A full page means there may be more.
	async sessions({ query = "", before = "" } = {}) {
		const args = { limit: SESSION_PAGE };
		if (query) args.query = query;
		if (before) args.before = before;
		const rows = await this.transport.call("flow.api.list_sessions", args);
		return {
			sessions: rows.map((row) => ({
				session_id: row.name,
				title: row.title,
				agent: row.agent,
				model: row.model,
				modified: row.modified,
			})),
			more: rows.length === SESSION_PAGE,
		};
	}

	async session(sid) {
		const data = await this.transport.call("flow.api.session", { session: sid });
		this.hooks.onSession?.(data);
		return this.sessionInfo(data);
	}

	sessionInfo(data) {
		const config = {
			auto_approve: data.auto_approve,
			title: data.title,
			agent: data.agent,
			model: data.model,
			cwd: null,
		};
		this.configs.set(data.name, config);
		return {
			session_id: data.name,
			title: data.title,
			agent: data.agent,
			model: data.model,
			latest_seq: 0,
			context_window: this.contextWindows.get(data.model) ?? null,
			config,
		};
	}

	async createSession(config = {}) {
		const data = await this.transport.call("flow.api.create_session", {
			agent: this.hooks.agent?.() ?? null,
			// a model the site no longer offers is left out, so the agent's is used
			model: this.modelRows.some((m) => m.name === config.model) ? config.model : null,
			auto_approve: config.auto_approve ? 1 : 0,
		});
		this.hooks.onSession?.(data);
		return {
			session_id: data.name,
			config: { ...this.sessionInfo(data).config, model: data.model },
		};
	}

	async entries(sid, since = 0, path = "active") {
		const data = await this.transport.call("flow.api.entries", { session: sid, since, path });
		const entries = (data.entries ?? []).map((row) => this.present(row, sid));
		this.hooks.onRows?.(sid, entries, { replace: path === "active" });
		return {
			...data,
			entries,
			preview: (data.preview ?? []).map((row) => this.present(row, sid)),
		};
	}

	stream(sid, since = 0) {
		return new SessionStream({
			socket: this.socket,
			session: sid,
			since,
			fetchEntries: (cursor) => this.entries(sid, cursor, "all"),
			present: (event) => {
				const row = this.present(event, sid);
				if (typeof row.seq === "number")
					this.hooks.onRows?.(sid, [row], { replace: false });
				return row;
			},
			onTerminal: () => this.syncSession(sid),
		});
	}

	// a run just ended and its own syncs may race this one: retry once, then stay quiet
	async syncSession(sid) {
		const sync = () => this.transport.call("flow.api.sync_session", { session: sid });
		const data = await sync()
			.catch(sync)
			.catch(() => null);
		if (data) this.hooks.onSession?.(data);
		return data;
	}

	async run(sid, message, attachments = []) {
		return this.transport.call("flow.api.run", { session: sid, message, attachments });
	}

	resume(sid, seq, answers) {
		return this.transport.call("flow.api.resume", {
			session: sid,
			answers,
			approval_seq: seq,
		});
	}

	abort(sid) {
		return this.transport.call("flow.api.abort", { session: sid });
	}

	cancelPending(sid) {
		return this.transport.call("flow.api.cancel_pending", { session: sid });
	}

	async setModel(sid, { model, reasoning_effort = null }) {
		const data = await this.transport.call("flow.api.set_model", {
			session: sid,
			model,
			reasoning_effort,
		});
		this.configs.set(sid, { ...this.configs.get(sid), model: data.model });
		return {
			model: data.model,
			context_window: this.contextWindows.get(data.model) ?? null,
		};
	}

	async patchConfig(sid, patch) {
		const config = { ...(this.configs.get(sid) ?? {}) };
		if ("title" in patch) {
			const data = await this.transport.call("flow.api.set_title", {
				session: sid,
				title: patch.title,
			});
			config.title = data.title;
		}
		if ("auto_approve" in patch) {
			const data = await this.transport.call("flow.api.set_auto_approve", {
				session: sid,
				auto_approve: patch.auto_approve ? 1 : 0,
			});
			config.auto_approve = data.auto_approve;
		}
		this.configs.set(sid, config);
		return { config };
	}

	deleteSession(sid) {
		return this.transport.call("flow.api.delete_session", { session: sid });
	}

	// --- attachments -----------------------------------------------------------

	async prepareAttachment(file, model) {
		const uploaded = await this.transport.uploadFile(file);
		try {
			const staged = await this.transport.call("flow.api.attach_file", {
				file: uploaded.name,
				model,
			});
			this.fileIds.set(staged.file_name, staged.file);
			return {
				id: staged.file,
				name: staged.file_name,
				kind: IMAGE_FILE.test(staged.file_name) ? "image" : "file",
			};
		} catch (error) {
			await this.discardAttachments([uploaded.name]).catch(() => {});
			throw error;
		}
	}

	discardAttachments(ids) {
		return this.transport.call("flow.api.cleanup_attachments", { attachments: ids });
	}

	async uploadAttachments(_sid, files) {
		const attachments = [];
		try {
			for (const file of files) attachments.push(await this.prepareAttachment(file));
			return { attachments };
		} catch (error) {
			await this.discardAttachments(attachments.map((item) => item.id)).catch(() => {});
			throw error;
		}
	}

	cleanupAttachments(sid, ids) {
		return this.transport.call("flow.api.cleanup_attachments", {
			session: sid,
			attachments: ids,
		});
	}

	// --- skills ----------------------------------------------------------------

	// the store asks a live session, or previews the agent a new chat would start with
	skills(sid) {
		return this.transport.call("flow.api.skills", { session: sid });
	}

	previewSkills() {
		return this.transport.call("flow.api.skills", { agent: this.hooks.agent?.() ?? null });
	}

	// --- feedback --------------------------------------------------------------

	submitFeedback(run, rating, comment = "") {
		return this.transport.call("flow.api.submit_feedback", { run_name: run, rating, comment });
	}
}
