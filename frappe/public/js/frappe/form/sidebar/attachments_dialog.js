Object.assign(frappe.ui.form.Attachments.prototype, {
	make_all_dialog() {
		this.all_dialog = new frappe.ui.Dialog({
			title: __("Attachments"),
			size: "small",
			fields: [
				{
					fieldtype: "Data",
					fieldname: "search",
					placeholder: __("Search attachments"),
				},
				{
					fieldtype: "HTML",
					fieldname: "selection_bar",
				},
				{
					fieldtype: "HTML",
					fieldname: "attachment_list",
				},
			],
			primary_action_label: __("Attach a file"),
			primary_action: () => {
				this.all_dialog.hide();
				this.new_attachment();
			},
		});

		this.all_dialog.$wrapper.addClass("attachments-dialog");
		const dialog = this.all_dialog;
		dialog.onhide = () => dialog.$wrapper.remove();
		this.all_dialog_list = $(this.all_dialog.get_field("attachment_list").wrapper)
			.removeClass("frappe-control")
			.addClass("attachments-dialog-list");
		$(this.all_dialog.get_field("search").input).on("input", () =>
			this.render_all_dialog_list()
		);

		this.selected_files = new Set();
		this.can_select_files = this.can_delete_attachment();
		if (this.can_select_files) this.make_selection_bar();
		this.render_all_dialog_list();
		this.all_dialog.show();
	},

	make_selection_bar() {
		const $bar = $(this.all_dialog.get_field("selection_bar").wrapper)
			.removeClass("frappe-control")
			.addClass("attachments-selection-bar").html(`
				<label class="attachments-select-all">
					<input type="checkbox">
					<span class="attachments-selection-label"></span>
				</label>`);
		this.$select_all = $bar.find("input").on("change", () => {
			const select = this.$select_all.prop("checked");
			this.visible_files.forEach((name) =>
				select ? this.selected_files.add(name) : this.selected_files.delete(name)
			);
			this.update_selection();
		});
		this.$selection_label = $bar.find(".attachments-selection-label");
		this.delete_selected_btn = frappe.ui
			.button({
				label: __("Delete"),
				icon: "trash-2",
				theme: "red",
				variant: "subtle",
				size: "sm",
				css_class: "attachments-delete-selected",
				onclick: () => this.delete_selected_attachments(),
			})
			.appendTo($bar);
	},

	update_selection() {
		if (!this.can_select_files) return;
		const count = this.selected_files.size;
		const visible_selected = this.visible_files.filter((name) =>
			this.selected_files.has(name)
		).length;
		this.$select_all
			.prop(
				"checked",
				visible_selected > 0 && visible_selected === this.visible_files.length
			)
			.prop(
				"indeterminate",
				visible_selected > 0 && visible_selected < this.visible_files.length
			)
			.prop("disabled", !this.visible_files.length);
		this.$selection_label.text(count ? __("{0} selected", [count]) : __("Select all"));
		this.delete_selected_btn
			.toggleClass("hidden", !count)
			.find(".es-button__label")
			.text(__("Delete {0}", [count]));
		this.all_dialog_list.find(".attachment-select").each((i, el) => {
			el.checked = this.selected_files.has(el.dataset.name);
		});
	},

	delete_selected_attachments() {
		const names = [...this.selected_files];
		const files = this.get_attachments().filter((a) => names.includes(a.file_name));
		const total = files.length;
		frappe.confirm(
			names.length === 1
				? __("Delete {0}? This can't be undone.", [
						frappe.utils.escape_html(names[0]).bold(),
				  ])
				: __("Delete {0} attachments? This can't be undone.", [names.length]),
			() => {
				const request = this.remove_attachments(files).then((result) => {
					if (result.failed) throw result;
					return result;
				});
				frappe.ui.toast.promise(request, {
					loading:
						total === 1
							? __("Deleting 1 attachment...")
							: __("Deleting {0} attachments...", [total]),
					success: ({ removed }) =>
						removed === 1
							? __("1 attachment deleted")
							: __("{0} attachments deleted", [removed]),
					error: ({ removed }) =>
						__("{0} of {1} attachments deleted", [removed || 0, total]),
				});
			}
		);
	},

	// a few at a time, then one refresh for all of them; the first failure (whose error
	// the server already showed) stops the rest
	async remove_attachments(files) {
		const queue = [...files];
		const removed = [];
		let failed = 0;
		const worker = async () => {
			while (queue.length) {
				const file = queue.shift();
				const { method, type, args } = this.get_remove_request(file.name);
				try {
					await frappe.xcall(method, args, type);
					removed.push(file.name);
				} catch (e) {
					failed++;
					queue.length = 0;
				}
			}
		};
		await Promise.all([1, 2, 3, 4].map(worker));
		this.frm.get_docinfo().attachments = this.get_attachments().filter(
			(a) => !removed.includes(a.name)
		);
		this.selected_files?.clear();
		this.refresh();
		this.frm.sidebar.reload_docinfo();
		return { removed: removed.length, failed };
	},

	render_all_dialog_list() {
		const txt = (this.all_dialog.get_value("search") || "").trim().toLowerCase();
		const seen = new Set();
		const attachments = this.get_attachments()
			.slice()
			.reverse()
			.filter((a) => !seen.has(a.file_name) && seen.add(a.file_name))
			.filter((a) => !txt || (a.file_name || "").toLowerCase().includes(txt));

		this.all_dialog
			.get_primary_btn()
			.toggleClass("hidden", !this.frm.has_perm("write") || this.max_reached());
		this.all_dialog_list.empty();
		this.visible_files = attachments.map((a) => a.file_name);
		attachments.forEach((attachment, index) => {
			const $row = this.make_attachment_row(attachment);
			if (this.can_select_files) {
				$(`<input type="checkbox" class="attachment-select">`)
					.attr({
						"data-name": attachment.file_name,
						"aria-label": __("Select {0}", [attachment.file_name]),
					})
					.on("click", (e) => {
						e.stopPropagation();
						const select = e.target.checked;
						const from = e.shiftKey ? this.last_ticked_index ?? index : index;
						const [start, end] = [Math.min(from, index), Math.max(from, index)];
						this.visible_files
							.slice(start, end + 1)
							.forEach((name) =>
								select
									? this.selected_files.add(name)
									: this.selected_files.delete(name)
							);
						this.last_ticked_index = index;
						this.update_selection();
					})
					// outside the name's ellipsis box, which would clip its focus ring
					.prependTo($row.find(".data-pill"));
			}
			this.all_dialog_list.append($row);
		});
		this.last_ticked_index = null;
		const existing = new Set(this.get_attachments().map((a) => a.file_name));
		this.selected_files?.forEach(
			(name) => existing.has(name) || this.selected_files.delete(name)
		);
		this.update_selection();
		if (!attachments.length) {
			$(`<div class="text-muted text-sm attachments-dialog-empty"></div>`)
				.text(txt ? __("No attachments match {0}", [txt]) : __("No attachments"))
				.appendTo(this.all_dialog_list);
		}
	},
});
