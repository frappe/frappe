// Example: per-doctype Kanban customization, loaded automatically via the meta
// bundle whenever a ToDo Kanban board opens (like todo_list.js for list views).
frappe.provide("frappe.kanban_next.settings");

frappe.kanban_next.settings["ToDo"] = {
	// Applies to ALL ToDo boards. Use `boards["<Board Name>"]` to scope to one.
	callbacks: {
		onCardMove(move) {
			frappe.show_alert({
				message: __("Moved {0} → {1}", [move.cardId, move.toColumn]),
				indicator: "blue",
			});
		},
	},

	// Extra right-click items appended to the default card menu.
	card_context_menu(todo, page) {
		return [
			{
				label: __("Mark as Closed"),
				icon: "circle-check",
				onclick: () =>
					frappe.db
						.set_value("ToDo", todo.name, "status", "Closed")
						.then(() => page.board.refresh()),
			},
		];
	},
};
