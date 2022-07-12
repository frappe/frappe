export class UndoManager {
	constructor({ frm }) {
		this.frm = frm;
		this.undo_stack = [];
		this.redo_stack = [];
	}
	record_change({ fieldname, old_value, new_value }) {
		this.undo_stack.push({ fieldname, old_value, new_value });
	}

	undo() {
		const change = this.undo_stack.pop();
		if (change) {
			this.frm.set_value(change.fieldname, change.old_value);
			this.redo_stack.push(change);
		} else {
			this.show_alert(__("Nothing left to undo"));
		}
	}

	redo() {
		const change = this.redo_stack.pop();
		if (change) {
			this.frm.set_value(change.fieldname, change.new_value);
			this.undo_stack.push(change);
		} else {
			this.show_alert(__("Nothing left to redo"));
		}
	}

	show_alert(msg) {
		// reduce duration
		// keyboard interactions shouldn't have long running
		frappe.show_alert(msg, 3);
	}

	erase_history() {
		this.undo_stack = [];
		this.redo_stack = [];
	}
}
