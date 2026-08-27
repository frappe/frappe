// Naming tab: two stacked sections — naming series (with live previews) and Document
// Naming Rules. Each is a shared `frappe.doctype_settings.section` scaffold over a
// frappe.ui.EmbeddedList table (used for the list only — its built-in header/search
// are intentionally not used here). Series reuse the Document Naming
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

// A titled section (shared scaffold) + an EmbeddedList table beneath it. Returns the
// list so callers can refresh().
function make_section($parent, { title, description, add_label, on_add }, list_opts) {
	const { $body, $actions } = frappe.doctype_settings.section($parent, { title, description });

	const list = new frappe.ui.EmbeddedList({
		wrapper: $("<div></div>").appendTo($body),
		show_search: false,
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
			.appendTo($actions);
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
			on_add: (refresh) => series_dialog(doctype, null, refresh),
		},
		{
			empty_message: __("This doctype isn't named by a series."),
			// Clicking a row edits that one series — rename its prefix and/or set the next
			// number — reusing the Document Naming Settings methods (no bulk dialog).
			on_row_click: (row) => series_dialog(doctype, row, () => list.refresh()),
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

// One dialog for both adding and editing a series (`row` is null for add)
// Naming Settings methods (get_current / preview_series / update_series /
// update_series_start) — the same the Naming Settings page uses.
async function series_dialog(doctype, row, refresh) {
	const is_edit = !!row;
	const original = is_edit ? row.series : "";

	const doc = await load_settings();
	doc.transaction_type = doctype;
	if (is_edit) doc.prefix = original;
	const current = is_edit ? await settings_call(doc, "get_current") : 0;

	const hint = __("e.g. {0}", ["SO-.YYYY.-"]);
	const preview_label = (next) => (next ? __("Next: {0}", [next]) : hint);

	const fields = [
		{
			fieldtype: "Data",
			fieldname: "series",
			label: __("Series"),
			reqd: 1,
			default: original,
			// Seed from the row we already have (edit) or the hint (add); refresh live.
			description: is_edit ? preview_label(row.next) : hint,
			async onchange() {
				const value = dialog.get_value("series");
				if (!value) {
					dialog.set_df_property("series", "description", hint);
					return;
				}
				doc.try_naming_series = value;
				const next =
					((await settings_call(doc, "preview_series")) || "").split("\n")[0] || "";
				dialog.set_df_property("series", "description", preview_label(next));
			},
		},
	];
	if (is_edit) {
		fields.push({
			fieldtype: "Int",
			fieldname: "current_value",
			label: __("Current value"),
			default: current,
			description: __("The next generated name continues after this number."),
		});
	}
	fields.push(
		{ fieldtype: "Section Break", label: __("Rules for configuring series"), collapsible: 1 },
		{
			fieldtype: "HTML",
			fieldname: "series_help",
			options: frappe.ui.NamingSeriesDialog.help_html(),
		}
	);

	const dialog = new frappe.ui.Dialog({
		title: is_edit ? __("Edit Series") : __("Add Series"),
		fields,
		primary_action_label: is_edit ? __("Update") : __("Add"),
		primary_action: async ({ series, current_value }) => {
			series = (series || "").trim();
			if (!series) return;

			const options = ((await settings_call(doc, "get_options")) || "")
				.split("\n")
				.map((s) => s.trim())
				.filter(Boolean);

			if (series !== original) {
				if (options.includes(series)) {
					frappe.ui.toast({
						message: __("Series already exists"),
						type: "warning",
					});
					return;
				}
				doc.naming_series_options = (
					is_edit
						? options.map((s) => (s === original ? series : s))
						: [...options, series]
				).join("\n");
				await settings_call(doc, "update_series");
			}

			if (is_edit && cint(current_value) !== cint(current)) {
				doc.prefix = series;
				doc.current_value = cint(current_value);
				await settings_call(doc, "update_series_start");
			}

			dialog.hide();
			frappe.ui.toast({
				message: is_edit ? __("Series updated") : __("Series added"),
				type: "success",
			});
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
	frappe.ui.toast({ message: __("Series removed"), type: "success" });
	refresh();
}

// Load the Document Naming Settings Single into client locals and resolve with it, so
// frappe.call({ doc }) (which reads the doc from locals by name) can drive its
// whitelisted instance methods. Calls reuse one doc and must stay sequential.
function load_settings() {
	const cached = frappe.get_doc(NAMING_SETTINGS, NAMING_SETTINGS);
	if (cached) return Promise.resolve(cached);

	return frappe
		.call({
			method: "frappe.desk.form.load.getdoc",
			type: "GET",
			args: { doctype: NAMING_SETTINGS, name: NAMING_SETTINGS },
		})
		.then(() => frappe.get_doc(NAMING_SETTINGS, NAMING_SETTINGS));
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
									frappe.ui.toast({
										message: __("Deleted"),
										type: "success",
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
