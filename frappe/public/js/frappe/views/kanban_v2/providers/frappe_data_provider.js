// Data access for the Kanban board; wraps kanban_board.py whitelisted methods.
const KANBAN_METHOD = "frappe.desk.doctype.kanban_board.kanban_board";

export class FrappeDataProvider {
	constructor(config) {
		this.config = config;
	}

	/** Update the active filters without recreating the provider. */
	setFilters(filters) {
		if (!this.config.reportview_args) this.config.reportview_args = {};
		this.config.reportview_args.filters = JSON.stringify(filters || []);
	}

	call(method, args) {
		return frappe.call({
			method: `${KANBAN_METHOD}.${method}`,
			args: {
				board_name: this.config.board_name,
				...this.config.reportview_args,
				...args,
			},
		});
	}

	/** Expand a compressed {keys, values, user_info} payload into card objects. */
	expandCards(compressed) {
		if (!compressed || !compressed.keys) return [];
		// Cache user_info from the payload so cards show full names and images.
		if (compressed.user_info) {
			frappe.update_user_info(compressed.user_info);
		}
		return frappe.utils.dict(compressed.keys, compressed.values);
	}

	// Fetch and cache user_info for User-link fields not already cached.
	async fetchMissingUserInfo(cards) {
		const meta = frappe.get_meta(this.config.doctype);
		if (!meta || !cards || !cards.length) return;
		const known = frappe.boot.user_info || {};
		const user_fields = meta.fields
			.filter((df) => df.fieldtype === "Link" && df.options === "User")
			.map((df) => df.fieldname)
			.concat("owner");

		const missing = new Set();
		for (const card of cards) {
			for (const fieldname of user_fields) {
				const user = card[fieldname];
				if (user && !known[user]) missing.add(user);
			}
		}
		if (!missing.size) return;

		const info =
			(await frappe.xcall("frappe.desk.form.load.get_user_info_for_viewers", {
				users: [...missing],
			})) || {};
		// Cache unknown ids as themselves so we stop re-fetching them.
		missing.forEach((user) => {
			if (!info[user]) info[user] = { fullname: user, name: user, email: user };
		});
		frappe.update_user_info(info);
	}

	async getBoardColumns() {
		const board = await frappe.db.get_doc("Kanban Board", this.config.board_name);
		return (board && board.columns) || [];
	}

	async loadBoard() {
		const [boardColumns, response] = await Promise.all([
			this.getBoardColumns(),
			this.call("get_kanban_board_data", {}),
		]);

		const raw = (response && response.message && response.message.columns) || {};
		const columns = [];
		const cards = {};

		for (const col of boardColumns) {
			if (col.status === "Archived") continue;
			const id = col.column_name;
			const bucket = raw[id] || { total: 0, cards: undefined };

			columns.push({
				id,
				title: id,
				color: col.indicator || "gray",
				status: col.status || "Active",
				total: bucket.total || 0,
			});
			cards[id] = this.expandCards(bucket.cards);
		}

		// One lookup for the whole board, not one per column.
		await this.fetchMissingUserInfo(Object.values(cards).flat());

		return { columns, cards };
	}

	async loadColumnPage(columnId, start, pageLength) {
		const response = await this.call("get_kanban_column_page", {
			column_name: columnId,
			kanban_start: start,
			kanban_page_length: pageLength,
		});
		const message = (response && response.message) || {};
		const cards = this.expandCards(message.cards);
		await this.fetchMissingUserInfo(cards);
		return { total: message.total || 0, cards };
	}

	/** Returns the column value the server saved, which it may have changed. */
	async moveCard(input) {
		const r = await frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: this.config.doctype,
				name: input.cardId,
				fieldname: this.config.field_name,
				value: input.toColumn,
			},
		});
		return r.message && r.message[this.config.field_name];
	}

	/** Returns the names that could not be moved, and the column value saved for each card. */
	async moveCards(cardIds, toColumn) {
		const r = await frappe.call({
			method: "frappe.client.bulk_update",
			args: {
				docs: cardIds.map((name) => ({
					doctype: this.config.doctype,
					docname: name,
					[this.config.field_name]: toColumn,
				})),
			},
		});
		const failed = ((r.message && r.message.failed_docs) || []).map((f) => f.doc.docname);
		const rows = await frappe.db.get_list(this.config.doctype, {
			filters: { name: ["in", cardIds] },
			fields: ["name", this.config.field_name],
			limit: cardIds.length,
		});
		const saved = Object.fromEntries(rows.map((d) => [d.name, d[this.config.field_name]]));
		return { failed, saved };
	}

	/** Persist the horizontal order of board columns. */
	async moveColumnOrder(columnIds) {
		await this.call("update_column_order", {
			order: JSON.stringify(columnIds || []),
		});
	}

	/** Calls `cb(name)` when a document of this doctype changes anywhere. */
	onRemoteUpdate(cb) {
		const doctype = this.config.doctype;
		frappe.realtime.doctype_subscribe(doctype);
		const handler = (data) => {
			if (data && data.doctype === doctype) cb(data.name);
		};
		frappe.realtime.on("list_update", handler);
		return () => frappe.realtime.off("list_update", handler);
	}
}
