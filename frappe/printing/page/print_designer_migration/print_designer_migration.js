frappe.pages["print-designer-migration"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Migrate Print Designer Formats"),
		single_column: true,
	});
	wrapper.migration = new PrintDesignerMigration(page);
};

frappe.pages["print-designer-migration"].on_page_show = function (wrapper) {
	wrapper.migration?.refresh();
};

const METHOD = "frappe.printing.page.print_designer_migration.print_designer_migration";
const CONVERTER = "frappe.printing.doctype.print_format.print_designer_converter";

class PrintDesignerMigration {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
	}

	refresh() {
		this.highlight = frappe.get_route()[1];
		frappe.xcall(`${METHOD}.get_print_designer_formats`).then((rows) => this.render(rows));
	}

	render(rows) {
		this.page.clear_primary_action();
		if (rows.some((row) => !row.converted && row.standard !== "Yes")) {
			this.page.set_primary_action(__("Convert All"), () => this.convert_all());
		}

		this.$body.empty();
		const $content = $(`<div class="flex flex-col gap-4 p-4"></div>`).appendTo(this.$body);
		$content.append(
			`<p class="text-p-sm text-ink-gray-5 max-w-lg m-0">${__(
				"Converting turns a Print Designer format into a print format editor format with the same name, so everything that prints with it keeps working. Preview shows both side by side first."
			)}</p>`
		);

		if (!rows.length) {
			$content.append(
				frappe.ui.empty_state({
					icon: "printer",
					title: __("Nothing to migrate"),
					description: __("This site has no Print Designer formats."),
					css_class: "border border-outline-gray-2 rounded-lg",
				})
			);
			return;
		}

		const $list = $(`<div class="border border-outline-gray-2 rounded-lg"></div>`);
		rows.forEach((row, i) => {
			const $row = this.render_row(row);
			if (i) $row.addClass("border-t border-outline-gray-2");
			$list.append($row);
		});
		$content.append($list);
		$list.find(".highlighted").get(0)?.scrollIntoView({ block: "center" });
	}

	render_row(row) {
		const escape = frappe.utils.escape_html;
		const badge = row.converted
			? { label: __("Converted"), theme: "green" }
			: { label: __("Print Designer"), theme: "gray" };
		const details = [__(row.doc_type)];
		if (row.disabled) details.push(__("Disabled"));
		if (row.converted && row.editor_format !== row.name) {
			details.push(__("Converted to {0}", [row.editor_format]));
			if (row.usage?.length) details.push(__("Still used: {0}", [row.usage.join(", ")]));
		}
		const $row = $(`
			<div class="flex items-center gap-4 px-4 py-3">
				<div class="flex flex-col gap-1 flex-1 min-w-0">
					<div class="flex items-center gap-2">
						<a class="text-base-medium text-ink-gray-8 truncate" href="${frappe.utils.get_form_link(
							"Print Format",
							row.name
						)}">${escape(row.name)}</a>
						${frappe.ui.badge.html({ ...badge, size: "sm" })}
					</div>
					<div class="text-sm text-ink-gray-5 truncate">${escape(details.join(" · "))}</div>
				</div>
				<div class="flex items-center gap-2 shrink-0"></div>
			</div>
		`);
		if (row.name === this.highlight) $row.addClass("highlighted bg-surface-gray-2");

		const $actions = $row.children().last();
		const add = (label, onclick, icon_right) =>
			$actions.append(frappe.ui.button({ label, onclick, icon_right }));
		if (row.converted && row.usage?.length) {
			add(__("Use Copy"), () => this.use_copy(row));
		} else if (row.converted) {
			add(
				__("Edit"),
				() => frappe.set_route("print-format-builder", row.editor_format),
				"arrow-up-right"
			);
		} else {
			if (row.sample) add(__("Preview"), () => this.preview(row));
			add(__("Convert"), () => this.convert(row));
			if (row.standard !== "Yes") add(__("Delete"), () => this.delete(row));
		}
		return $row;
	}

	preview(row) {
		const pdf = (method, args) =>
			`/api/method/${method}?${new URLSearchParams(args).toString()}#toolbar=0`;
		const pane = (title) => `
			<div class="flex flex-col gap-2 flex-1 min-w-0">
				<div class="text-sm text-ink-gray-5">${title}</div>
				<iframe class="print-designer-preview w-full border border-outline-gray-2 rounded"></iframe>
			</div>`;
		const dialog = new frappe.ui.Dialog({
			title: __("Preview {0}", [row.name]),
			size: "extra-large",
			fields: [
				{
					fieldname: "document",
					fieldtype: "Link",
					options: row.doc_type,
					label: __(row.doc_type),
					default: row.sample,
					onchange: () => load(),
				},
				{
					fieldname: "panes",
					fieldtype: "HTML",
					options: `<div class="flex gap-4">${pane(__("Print Designer"))}${pane(
						__("After converting")
					)}</div>`,
				},
			],
			primary_action_label: __("Convert"),
			primary_action: () => {
				dialog.hide();
				this.convert(row);
			},
		});
		const load = () => {
			const name = dialog.get_value("document");
			if (!name) return;
			const [original, converted] = dialog.fields_dict.panes.$wrapper.find("iframe");
			original.src = pdf("frappe.utils.print_format.download_pdf", {
				doctype: row.doc_type,
				name,
				format: row.name,
			});
			converted.src = pdf(`${METHOD}.preview_conversion`, { print_format: row.name, name });
		};
		dialog.show();
		load();
	}

	convert(row) {
		const escape = frappe.utils.escape_html;
		return frappe
			.xcall(`${CONVERTER}.convert`, { print_format: row.name })
			.then(({ name, notes, usage }) => {
				frappe.show_alert({
					message: __("Converted {0}", [row.name]),
					indicator: "green",
				});
				this.refresh();
				if (!usage.length) return this.show_notes(notes);
				frappe.confirm(
					__(
						"{0} belongs to its app, so it was converted as {1}. {0} is in use: {2}. Use {1} there instead?",
						[
							`<b>${escape(row.name)}</b>`,
							`<b>${escape(name)}</b>`,
							usage.map((place) => escape(place)).join(", "),
						]
					),
					() =>
						frappe
							.xcall(`${CONVERTER}.use_editor_copy`, { print_format: row.name })
							.then(() => {
								frappe.show_alert({
									message: __("{0} now prints with {1}", [row.name, name]),
									indicator: "green",
								});
								this.refresh();
								this.show_notes(notes);
							}),
					() => this.show_notes(notes)
				);
			});
	}

	use_copy(row) {
		return frappe
			.xcall(`${CONVERTER}.use_editor_copy`, { print_format: row.name })
			.then(() => {
				frappe.show_alert({
					message: __("{0} now prints with {1}", [row.name, row.editor_format]),
					indicator: "green",
				});
				this.refresh();
			});
	}

	delete(row) {
		const escape = frappe.utils.escape_html;
		return frappe
			.xcall(`${METHOD}.get_print_format_usage`, { print_format: row.name })
			.then((usage) => {
				if (usage.length) {
					frappe.msgprint({
						title: __("Cannot Delete"),
						message: __("{0} is still in use: {1}. Pick another format there first.", [
							`<b>${escape(row.name)}</b>`,
							usage.map((place) => escape(place)).join(", "),
						]),
					});
					return;
				}
				frappe.confirm(
					__("Delete <b>{0}</b>? This cannot be undone.", [escape(row.name)]),
					() =>
						frappe
							.xcall("frappe.client.delete", {
								doctype: "Print Format",
								name: row.name,
							})
							.then(() => {
								frappe.show_alert({
									message: __("Deleted {0}", [row.name]),
									indicator: "green",
								});
								this.refresh();
							})
				);
			});
	}

	show_notes(notes) {
		if (!notes.length) return;
		frappe.msgprint({
			title: __("Converted with changes"),
			message: notes.map((note) => frappe.utils.escape_html(note)).join("<br>"),
		});
	}

	convert_all() {
		frappe.confirm(
			__(
				"Convert every Print Designer format on this list? Preview a few first if you are unsure. Formats that belong to an app are converted one by one."
			),
			() =>
				frappe
					.xcall(`${METHOD}.convert_all`, {}, "POST", { freeze: true })
					.then(({ converted, failed }) => {
						frappe.show_alert({
							message: __("Converted {0} formats", [converted.length]),
							indicator: "green",
						});
						if (failed.length) {
							frappe.msgprint({
								title: __("Some formats were not converted"),
								message: __("{0}. The details are in the Error Log.", [
									failed
										.map((name) => frappe.utils.escape_html(name))
										.join(", "),
								]),
								indicator: "orange",
							});
						}
						this.refresh();
					})
		);
	}
}
