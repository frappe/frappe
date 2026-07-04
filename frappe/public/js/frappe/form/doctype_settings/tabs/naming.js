// Naming tab: two stacked sections — naming series (with live previews) and Document
// Naming Rules. Each section renders its own header (matching the dialog's panel-title
// style) over a frappe.ui.EmbeddedList table (used for the list only — its built-in
// header/search are intentionally not used here). Series reuse the Document Naming
// Settings instance methods (the same the settings page uses) by loading that Single
// into locals; rules use generic db APIs. No custom backend.
const NAMING_SETTINGS = "Document Naming Settings";

frappe.doctype_settings.register("naming", function (panel, doctype) {
	panel.set_view({
		render: (p) => {
			const $body = p.body.empty();
			// Series management lives behind the System-Manager-only Naming Settings, and only
			// applies to doctypes named by a series (i.e. those with a `naming_series` field —
			// the same signal get_options / NamingSeriesDialog key on). Hide it otherwise.
			if (
				frappe.user.has_role("System Manager") &&
				frappe.meta.get_docfield(doctype, "naming_series")
			) {
				make_series_section($body, doctype);
			}
			make_rules_section($body, doctype, panel);
		},
	});
});

// Render a section header (reusing the dialog's panel-title classes for a consistent
// look) + an EmbeddedList table beneath it. Returns the list so callers can refresh().
function make_section($parent, { title, description, add_label, on_add }, list_opts) {
	const $section = $('<div class="dts-section"></div>').appendTo($parent);
	const $header = $(`
		<div class="settings-dialog-panel-header">
			<div class="settings-dialog-panel-heading">
				<div class="settings-dialog-panel-title"></div>
				<div class="settings-dialog-panel-description"></div>
			</div>
			<div class="settings-dialog-panel-actions"></div>
		</div>
	`).appendTo($section);
	$header.find(".settings-dialog-panel-title").text(title);
	$header.find(".settings-dialog-panel-description").text(description);

	const list = new frappe.ui.EmbeddedList({
		wrapper: $("<div></div>").appendTo($section),
		...list_opts,
	});
	list.refresh();

	if (add_label) {
		frappe.ui
			.button({
				label: add_label,
				icon: "plus",
				onclick: () => on_add(() => list.refresh()),
			})
			.appendTo($header.find(".settings-dialog-panel-actions"));
	}
	return list;
}

// ── Naming series (with preview) ──
function make_series_section($body, doctype) {
	let list;
	list = make_section(
		$body,
		{
			title: __("Naming Series"),
			description: __(
				"Configure naming series options for {0}. You can choose a series when creating a document.",
				[doctype]
			),
			add_label: __("Add Series"),
			on_add: (refresh) => add_series(doctype, refresh),
		},
		{
			empty_message: __("This doctype isn't named by a series."),
			// Clicking a row edits that one series — rename its prefix and/or set the next
			// number — reusing the Document Naming Settings methods (no bulk dialog).
			on_row_click: (row) => edit_series(doctype, row, () => list.refresh()),
			// Reuse the settings methods: read the options, then preview each series. Calls
			// share one locals doc, so they run sequentially.
			get_data: async () => {
				const doc = await load_settings();
				doc.transaction_type = doctype;
				const options = await settings_call(doc, "get_options");
				const series = (options || "")
					.split("\n")
					.map((s) => s.trim())
					.filter(Boolean);

				const rows = [];
				for (const s of series) {
					doc.try_naming_series = s;
					const preview = await settings_call(doc, "preview_series");
					rows.push({ series: s, next: (preview || "").split("\n")[0] || "" });
				}
				return rows;
			},
			columns: [
				{ label: __("Series"), fieldname: "series" },
				{
					label: __("Preview"),
					fieldname: "next",
					// <samp> = bootstrap's monospace font with no extra color/padding (unlike <code>).
					render: (row) => `<samp>${frappe.utils.escape_html(row.next || "")}</samp>`,
				},
				{
					type: "actions",
					actions: [
						{
							icon: "trash-2",
							label: __("Delete"),
							danger: true,
							confirm: __("Delete series {0}?"),
							confirm_field: "series",
							action: (row, refresh) => remove_series(doctype, row.series, refresh),
						},
					],
				},
			],
		}
	);
	return list;
}

// Add a series by appending to the options list and reusing update_series (the same
// path the Naming Settings page uses — it validates the series and rejects duplicates).
function add_series(doctype, refresh) {
	frappe.prompt(
		{
			fieldtype: "Data",
			label: __("New series"),
			fieldname: "series",
			reqd: 1,
			description: __("e.g. {0}", ["SO-.YYYY.-"]),
		},
		async ({ series }) => {
			const doc = await load_settings();
			doc.transaction_type = doctype;
			const options = (await settings_call(doc, "get_options")) || "";
			const list_options = options
				.split("\n")
				.map((s) => s.trim())
				.filter(Boolean);
			if (list_options.includes(series.trim())) {
				frappe.show_alert({ message: __("Series already exists"), indicator: "orange" });
				return;
			}
			doc.naming_series_options = [...list_options, series.trim()].join("\n");
			frappe.call({
				method: "update_series",
				doc,
				callback: () => {
					frappe.show_alert({ message: __("Series added"), indicator: "green" });
					refresh();
				},
			});
		},
		__("Add series")
	);
}

// Edit a single series: rename its prefix and/or set its current counter, with a live
// preview shown in the Series field's description and the shared "rules" help. Reuses the
// Document Naming Settings methods (get_current / preview_series / update_series /
// update_series_start) — the same the Naming Settings page uses — instead of the bulk dialog.
async function edit_series(doctype, row, refresh) {
	const series = row.series;
	const doc = await load_settings();
	doc.transaction_type = doctype;
	doc.prefix = series;
	const current = await settings_call(doc, "get_current");

	const preview_label = (next) => (next ? __("Next: {0}", [next]) : "");

	const dialog = new frappe.ui.Dialog({
		title: __("Edit Series"),
		fields: [
			{
				fieldtype: "Data",
				fieldname: "series",
				label: __("Series"),
				reqd: 1,
				default: series,
				// Seed the preview from the row we already have; refresh it live on change.
				description: preview_label(row.next),
				async onchange() {
					const value = dialog.get_value("series");
					if (!value) {
						dialog.set_df_property("series", "description", "");
						return;
					}
					doc.try_naming_series = value;
					const next =
						((await settings_call(doc, "preview_series")) || "").split("\n")[0] || "";
					dialog.set_df_property("series", "description", preview_label(next));
				},
			},
			{
				fieldtype: "Int",
				fieldname: "current_value",
				label: __("Current value"),
				default: current,
				description: __("The next generated name continues after this number."),
			},
			{
				fieldtype: "Section Break",
				label: __("Rules for configuring series"),
				collapsible: 1,
			},
			{
				fieldtype: "HTML",
				fieldname: "series_help",
				options: frappe.ui.NamingSeriesDialog.help_html(),
			},
		],
		primary_action_label: __("Update"),
		primary_action: async ({ series: new_series, current_value }) => {
			new_series = (new_series || "").trim();

			// Rename: swap the prefix in the options list and reuse update_series (it validates).
			if (new_series && new_series !== series) {
				const options = ((await settings_call(doc, "get_options")) || "")
					.split("\n")
					.map((s) => s.trim())
					.filter(Boolean);
				if (options.includes(new_series)) {
					frappe.show_alert({
						message: __("Series already exists"),
						indicator: "orange",
					});
					return;
				}
				doc.naming_series_options = options
					.map((s) => (s === series ? new_series : s))
					.join("\n");
				await settings_call(doc, "update_series");
			}

			// Counter: set the current value on the (possibly renamed) series.
			if (cint(current_value) !== cint(current)) {
				doc.prefix = new_series || series;
				doc.current_value = cint(current_value);
				await settings_call(doc, "update_series_start");
			}

			dialog.hide();
			frappe.show_alert({ message: __("Series updated"), indicator: "green" });
			refresh();
		},
	});

	dialog.show();
}

// Remove a series by dropping it from the options list (reuses update_series).
async function remove_series(doctype, series, refresh) {
	const doc = await load_settings();
	doc.transaction_type = doctype;
	const options = ((await settings_call(doc, "get_options")) || "")
		.split("\n")
		.map((s) => s.trim())
		.filter(Boolean)
		.filter((s) => s !== series);
	doc.naming_series_options = options.join("\n");
	await settings_call(doc, "update_series");
	frappe.show_alert({ message: __("Series removed"), indicator: "green" });
	refresh();
}

// Load the Document Naming Settings Single into client locals and resolve with it, so
// frappe.call({ doc }) (which reads the doc from locals by name) can drive its
// whitelisted instance methods. Calls reuse one doc and must stay sequential.
function load_settings() {
	return new Promise((resolve) =>
		frappe.model.with_doc(NAMING_SETTINGS, NAMING_SETTINGS, () =>
			resolve(frappe.get_doc(NAMING_SETTINGS, NAMING_SETTINGS))
		)
	);
}

function settings_call(doc, method) {
	return frappe.call({ method, doc }).then((r) => r.message);
}

// ── Document Naming Rules ──
function make_rules_section($body, doctype, panel) {
	const open = (name) => {
		panel.dialog.hide();
		frappe.set_route("Form", "Document Naming Rule", name);
	};

	return make_section(
		$body,
		{
			title: __("Naming Rules"),
			description: __(
				"Configure conditional naming rules for {0}. Rules are applied in priority order.",
				[doctype]
			),
			add_label: __("New"),
			on_add: () => {
				panel.dialog.hide();
				frappe.new_doc("Document Naming Rule", { document_type: doctype });
			},
		},
		{
			empty_message: __("No rules found."),
			// Add a derived `status` label for the badge column.
			get_data: () =>
				frappe.db
					.get_list("Document Naming Rule", {
						filters: { document_type: doctype },
						fields: ["name", "prefix", "counter", "priority", "disabled"],
						order_by: "priority desc, name asc",
						limit: 0,
					})
					.then((rows) =>
						rows.map((r) => ({
							...r,
							status: r.disabled ? __("Disabled") : __("Enabled"),
						}))
					),
			on_row_click: (row) => open(row.name),
			columns: [
				{
					label: __("Prefix"),
					fieldname: "prefix",
					render: (row) => frappe.utils.escape_html(row.prefix || row.name),
				},
				{ label: __("Counter"), fieldname: "counter", align: "center" },
				{ label: __("Priority"), fieldname: "priority", align: "center" },
				{
					label: __("Status"),
					type: "badge",
					fieldname: "status",
					color: (row) => (row.disabled ? "gray" : "green"),
				},
				{
					type: "actions",
					actions: [
						{ icon: "pencil", label: __("Edit"), action: (row) => open(row.name) },
						{
							icon: "trash-2",
							label: __("Delete"),
							danger: true,
							confirm: __("Delete naming rule {0}?"),
							confirm_field: "prefix",
							action: (row, refresh) =>
								frappe.db.delete_doc("Document Naming Rule", row.name).then(() => {
									frappe.show_alert({
										message: __("Deleted"),
										indicator: "green",
									});
									refresh();
								}),
						},
					],
				},
			],
		}
	);
}
