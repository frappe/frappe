export class UndoManager {
	constructor({ frm }) {
		this.frm = frm;
		this.undo_stack = [];
		this.redo_stack = [];
	}
	record_change({
		fieldname,
		old_value,
		new_value,
		doctype,
		docname,
		is_child,
	}) {
		this.undo_stack.push({
			fieldname,
			old_value,
			new_value,
			doctype,
			docname,
			is_child,
		});
	}

	erase_history() {
		this.undo_stack = [];
		this.redo_stack = [];
	}

	undo() {
		const change = this.undo_stack.pop();
		if (change) {
			this.#apply_change(change);
			this.#push_reverse_entry(change, this.redo_stack);
		} else {
			this.#show_alert(__("Nothing left to undo"));
		}
	}

	redo() {
		const change = this.redo_stack.pop();
		if (change) {
			this.#apply_change(change);
			this.#push_reverse_entry(change, this.undo_stack);
		} else {
			this.#show_alert(__("Nothing left to redo"));
		}
	}

	#push_reverse_entry(change, stack) {
		stack.push({
			...change,
			new_value: change.old_value,
			old_value: change.new_value,
		});
	}

	#apply_change(change) {
		if (change.is_child) {
			frappe.model.set_value(
				change.doctype,
				change.docname,
				change.fieldname,
				change.old_value
			);
		} else {
			this.frm.set_value(change.fieldname, change.old_value);
			this.frm.scroll_to_field(change.fieldname, false);
		}
	}

	#show_alert(msg) {
		// reduce duration
		// keyboard interactions shouldn't have long running annoying toasts
		frappe.show_alert(msg, 3);
	}
}
