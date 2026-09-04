/**
 * FrappeDataProvider — Desk data-access boundary. Wraps the existing whitelisted
 * methods in frappe/desk/doctype/kanban_board/kanban_board.py without changing
 * them. Reportview args (doctype, fields, filters, order_by) come from the Desk
 * page context via config.reportview_args.
 *
 * config: { doctype, board_name, reportview_args? }
 */
const KB = "frappe.desk.doctype.kanban_board.kanban_board";

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
			method: `${KB}.${method}`,
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
		// reportview.compress ships the assignees'/owners' user_info alongside
		// the rows — merge it into the boot cache so frappe.user_info(user)
		// resolves real full names + images on cards and hovercards.
		if (compressed.user_info) {
			frappe.update_user_info(compressed.user_info);
		}
		return frappe.utils.dict(compressed.keys, compressed.values);
	}

	/**
	 * reportview only ships names for assignees, so a User link field (owner,
	 * allocated_to, …) arrives as a bare id and frappe.user_info() has nothing
	 * to show. Look up every id we have not seen yet in one call and put it in
	 * the boot cache, so cards render full names straight away.
	 */
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
		// Ids the server knows nothing about (deleted users) are cached as
		// themselves, so the board stops asking for them.
		missing.forEach((user) => {
			if (!info[user]) info[user] = { fullname: user, name: user, email: user };
		});
		frappe.update_user_info(info);
	}

	parseOrder(order) {
		if (!order) return [];
		try {
			const parsed = JSON.parse(order);
			return Array.isArray(parsed) ? parsed : [];
		} catch (e) {
			return [];
		}
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
				order: this.parseOrder(col.order),
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

	async moveCard(input) {
		await this.call("update_order_for_single_card", {
			docname: input.cardId,
			from_colname: input.fromColumn,
			to_colname: input.toColumn,
			from_order: JSON.stringify(input.fromOrder),
			to_order: JSON.stringify(input.toOrder),
		});
	}

	/** Persist final orders for one or more columns in a single request (bulk moves). */
	async updateOrder(orderByColumn) {
		await this.call("update_order", {
			order: JSON.stringify(orderByColumn || {}),
			// This is an explicit move, so a missing write permission should error
			// (and roll the UI back) rather than silently no-op like the classic
			// board's on-load order sync.
			throw_on_no_write: 1,
		});
	}

	/** Persist the horizontal order of board columns. */
	async moveColumnOrder(columnIds) {
		await this.call("update_column_order", {
			order: JSON.stringify(columnIds || []),
		});
	}

	onRemoteUpdate(cb) {
		const event = "kanban_board_update";
		const handler = (data) => {
			if (!data || data.board_name === this.config.board_name) cb();
		};
		frappe.realtime.on(event, handler);
		return () => frappe.realtime.off(event, handler);
	}
}
