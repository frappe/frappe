frappe.provide('frappe.file_manager');

frappe.file_manager = function() {
	let files_to_move = [];
	let	old_folder = null;
	let new_folder = null;

	function cut(files, old_folder_) {
		files_to_move = files;
		old_folder = old_folder_;
	}

	function paste(new_folder_) {
		return new Promise((resolve, reject) => {
			if (files_to_move.length === 0 || !old_folder) {
				reset();
				resolve();
				return;
			}
			new_folder = new_folder_;

			frappe.call({
				method:"frappe.core.doctype.file.file.move_file",
				args: {
					file_list: files_to_move,
					new_parent: new_folder,
					old_parent: old_folder
				},
				callback: r => {
					reset();
					resolve(r);
				}
			}).fail(reject);
		});
	}

	function reset() {
		files_to_move = [];
		old_folder = null;
		new_folder = null;
	}

	return {
		cut,
		paste,
		get can_paste() {
			return Boolean(files_to_move.length > 0 && old_folder);
		},
		get old_folder() {
			return old_folder;
		},
		get files_to_move() {
			return files_to_move;
		}
	};
}();
