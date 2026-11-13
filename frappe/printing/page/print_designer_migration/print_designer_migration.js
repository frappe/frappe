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

const STATES = {
	"Not converted": { theme: "gray", label: __("Not converted") },
	Converted: { theme: "blue", label: __("Converted") },
	"Switched over": { theme: "green", label: __("Switched over") },
};

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
		if (rows.some((row) => row.state === "Not converted")) {
			this.page.set_primary_action(__("Convert All"), () => this.convert_all());
		}

		this.$body.empty();
		const $content = $(`<div class="flex flex-col gap-4 p-4"></div>`).appendTo(this.$body);
		$content.append(
			`<p class="text-p-sm text-ink-gray-5 max-w-lg m-0">${__(
				"Convert each Print Designer format to an editor format and check the copy. Switching over points the default format, notifications and auto repeat at the copy and disables the original. Once nothing uses the original, it can be deleted."
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
		const state = STATES[row.state];
		const escape = frappe.utils.escape_html;
		const details = [__(row.doc_type)];
		if (row.editor_format) details.push(__("Copy: {0}", [row.editor_format]));
		if (row.state === "Switched over" && !row.can_delete) {
			details.push(__("Standard format, kept by its app"));
		}
		const $row = $(`
			<div class="flex items-center gap-4 px-4 py-3">
				<div class="flex flex-col gap-1 flex-1 min-w-0">
					<div class="flex items-center gap-2">
						<a class="text-base-medium text-ink-gray-8 truncate">${escape(row.name)}</a>
						${frappe.ui.badge.html({ label: state.label, theme: state.theme, size: "sm" })}
					</div>
					<div class="text-sm text-ink-gray-5 truncate">${escape(details.join(" · "))}</div>
				</div>
				<div class="flex items-center gap-2 shrink-0"></div>
			</div>
		`);
		if (row.name === this.highlight) $row.addClass("highlighted bg-surface-gray-2");
		$row.find("a").on("click", () => frappe.set_route("Form", "Print Format", row.name));

		const $actions = $row.children().last();
		const add = (label, onclick, icon_right) =>
			$actions.append(frappe.ui.button({ label, onclick, icon_right }));
		if (row.state === "Not converted") {
			add(__("Convert"), () => this.convert(row));
		} else {
			add(
				__("Open"),
				() => frappe.set_route("print-format-builder", row.editor_format),
				"arrow-up-right"
			);
		}
		if (row.state === "Converted") {
			add(__("Switch Over"), () => this.switch_over(row));
		}
		if (row.can_delete) {
			add(__("Delete Original"), () => this.delete_original(row));
		}
		return $row;
	}

	convert(row) {
		return frappe
			.xcall(`${CONVERTER}.create_editor_format`, { print_format: row.name })
			.then(({ name, notes }) => {
				frappe.show_alert({ message: __("Converted to {0}", [name]), indicator: "green" });
				if (notes.length) {
					frappe.msgprint({
						title: __("Converted with changes"),
						message: notes.map((note) => frappe.utils.escape_html(note)).join("<br>"),
					});
				}
				this.refresh();
			});
	}

	convert_all() {
		return frappe
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
							failed.map((name) => frappe.utils.escape_html(name)).join(", "),
						]),
						indicator: "orange",
					});
				}
				this.refresh();
			});
	}

	switch_over(row) {
		const escape = frappe.utils.escape_html;
		frappe.confirm(
			__(
				"Everything that prints with <b>{0}</b>, like the default format, notifications and auto repeat, will use <b>{1}</b> instead, and <b>{0}</b> will be disabled.",
				[escape(row.name), escape(row.editor_format)]
			),
			() =>
				frappe
					.xcall(`${CONVERTER}.replace_with_editor_format`, {
						print_format: row.name,
						editor_format: row.editor_format,
					})
					.then(() => {
						frappe.show_alert({
							message: __("{0} now prints with {1}", [row.name, row.editor_format]),
							indicator: "green",
						});
						this.refresh();
					})
		);
	}

	delete_original(row) {
		frappe.confirm(
			__("Delete <b>{0}</b>? This cannot be undone.", [frappe.utils.escape_html(row.name)]),
			() =>
				frappe
					.xcall("frappe.client.delete", { doctype: "Print Format", name: row.name })
					.then(() => {
						frappe.show_alert({
							message: __("Deleted {0}", [row.name]),
							indicator: "green",
						});
						this.refresh();
					})
		);
	}
}
