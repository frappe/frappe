frappe.provide("frappe.core");

frappe.ui.form.on("Workflow", {
	onload: function (frm) {
		frm.set_query("document_type", { issingle: 0, istable: 0 });
	},
	refresh: function (frm) {
		frm.layout.message.empty();
		let title, note;
		let workflow_builder_url = "/app/workflow-builder";
		let msg = __(
			"Workflow Builder allows you to create workflows visually. You can drag and drop states and link them to create transitions. Also you can update thieir properties from the sidebar."
		);

		if (frm.is_new()) {
			title = __("Create your workflow visually using the Workflow Builder.");
		} else {
			title = __("Edit your workflow visually using the Workflow Builder.");
			note = __(
				"NOTE: If you add states or transitions in the table, it will be reflected in the Workflow Builder but you will have to position them manually. Also Workflow Builder is currently in <b>BETA</b>."
			);
			workflow_builder_url += "/" + frm.doc.name;
		}

		let message = `
		<div class="flex">
			<div class="mr-3"><img style="border-radius: var(--border-radius-md)" width="600" src="/assets/frappe/images/workflow-builder.gif"></div>
			<div>
				<p style="font-size: var(--text-xl)">${title}</p>
				<p>${msg}</p>
				<p class="mb-3">${note || ""}</p>
				<div>
					<a class="btn btn-primary btn-sm" href="${workflow_builder_url}">
						${__("Workflow Builder")} ${frappe.utils.icon("right", "xs")}
					</a>
				</div>
			</div>
		</div>
		`;

		frm.layout.show_message(message);

		if (frm.doc.document_type) {
			frm.add_custom_button(__("Go to {0} List", [frm.doc.document_type]), () => {
				frappe.set_route("List", frm.doc.document_type);
			});
		}

		frm.events.update_field_options(frm);
		frm.ignore_warning = frm.is_new() ? true : false;
		frm.state_status_mapping = {};

		if (frm.is_new()) {
			return;
		}
		frm.doc.states.forEach((row) => {
			frm.state_status_mapping[row.state] = row.doc_status;
		});

		frm.states = null;
		frm.trigger("make_state_table");
		frm.trigger("get_orphaned_states_and_count").then(() => {
			frm.trigger("render_state_table");
		});
	},
	validate: async (frm) => {
		if (frm.doc.is_active && (!frm.doc.states.length || !frm.doc.transitions.length)) {
			let message = "Workflow must have atleast one state and transition";
			frappe.throw({
				message: __(message),
				title: __("Missing Values Required"),
				indicator: "orange",
			});
		}

		if (frm.ignore_warning) {
			return;
		}

		let updated_states = [];
		frm.doc.states.forEach((row) => {
			if (
				frm.state_status_mapping[row.state] &&
				frm.state_status_mapping[row.state] !== row.doc_status
			) {
				updated_states.push(row.state);
			}
		});

		if (updated_states.length) {
			frm.doc._update_state_docstatus = await create_docstatus_change_warning(
				updated_states
			);
		}

		return frm.trigger("get_orphaned_states_and_count").then(() => {
			if (frm.states && frm.states.length) {
				frappe.validated = false;
				frm.trigger("create_warning_dialog");
			}
		});
	},
	document_type: function (frm) {
		frm.events.update_field_options(frm);
	},
	update_field_options: function (frm) {
		var doc = frm.doc;
		if (!doc.document_type) {
			return;
		}
		frappe.model.with_doctype(doc.document_type, () => {
			const fieldnames = frappe
				.get_meta(doc.document_type)
				.fields.filter((field) => !frappe.model.no_value_type.includes(field.fieldtype))
				.map((field) => field.fieldname);

			frm.fields_dict.states.grid.update_docfield_property(
				"update_field",
				"options",
				[""].concat(fieldnames)
			);
		});
	},
	create_warning_dialog: function (frm) {
		const warning_html = `<p class="bold">
				${__("Are you sure you want to save this document?")}
			</p>
			<p>
				${__(
					"There are documents which have workflow states that do not exist in this Workflow. It is recommended that you add these states to the Workflow and change their states before removing these states."
				)}
			</p>`;
		const message_html = warning_html + frm.state_table_html;
		let proceed_action = () => {
			frm.ignore_warning = true;
			frm.save();
		};

		frappe.warn(
			__("Workflow States Don't Exist"),
			message_html,
			proceed_action,
			__("Save Anyway")
		);
	},
	set_table_html: function (frm) {
		const promises = frm.states.map((r) => {
			const state = r[frm.doc.workflow_state_field];
			return frappe.utils.get_indicator_color(state).then((color) => {
				return `<tr>
				<td>
					<div class="indicator ${color}">
						<a class="text-muted orphaned-state">${r[frm.doc.workflow_state_field]}</a>
					</div>
				</td>
				<td>${r.count}</td></tr>`;
			});
		});

		Promise.all(promises).then((rows) => {
			const rows_html = rows.join("");
			frm.state_table_html = `<table class="table state-table table-bordered" style="margin:0px; width: 65%">
				<thead style="font-size: 12px">
					<tr class="text-muted">
						<th>${__("State")}</th>
						<th>${__("Count")}</th>
					</tr>
				</thead>
				<tbody>
					${rows_html}
				</tbody>
			</table>`;
		});
	},
	get_orphaned_states_and_count: function (frm) {
		if (frm.is_new()) return;
		let states_list = [];
		frm.doc.states.map((state) => states_list.push(state.state));
		return frappe
			.xcall("frappe.workflow.doctype.workflow.workflow.get_workflow_state_count", {
				doctype: frm.doc.document_type,
				workflow_state_field: frm.doc.workflow_state_field,
				states: states_list,
			})
			.then((result) => {
				if (result && result.length) {
					frm.states = result;
					return frm.trigger("set_table_html");
				}
			});
	},
	make_state_table: function (frm) {
		const wrapper = frm.get_field("states").$wrapper;
		if (frm.state_table) {
			frm.state_table.empty();
		}
		frm.state_table = $(`<div class="state-table"><div>`).insertAfter(wrapper);
	},
	render_state_table: function (frm) {
		if (frm.states && frm.states.length) {
			const form_state_table_html = `<p class="text-muted small" style="margin-top: 30px">
					${"Document States that do not exist in your Workflow"}
				</p>
				${frm.state_table_html}
				</div>`;
			frm.state_table.html(form_state_table_html);

			$(frm.state_table)
				.find("a.orphaned-state")
				.on("click", (e) => {
					const state = $(e.currentTarget).text();
					let filters = {};
					filters[frm.doc.workflow_state_field] = state;
					frappe.set_route("List", frm.doc.document_type, filters);
				});
		}
	},
});

frappe.ui.form.on("Workflow Document State", {
	state: function (_, cdt, cdn) {
		var row = locals[cdt][cdn];
		delete row.workflow_builder_id;
	},

	states_remove: function (frm) {
		frm.trigger("get_orphaned_states_and_count").then(() => {
			frm.trigger("render_state_table");
		});
	},
});

frappe.ui.form.on("Workflow Transition", {
	state: function (_, cdt, cdn) {
		var row = locals[cdt][cdn];
		delete row.workflow_builder_id;
	},

	next_state: function (_, cdt, cdn) {
		var row = locals[cdt][cdn];
		delete row.workflow_builder_id;
	},

	action: function (_, cdt, cdn) {
		var row = locals[cdt][cdn];
		delete row.workflow_builder_id;
	},

	states_remove: function (frm) {
		frm.trigger("get_orphaned_states_and_count").then(() => {
			frm.trigger("render_state_table");
		});
	},
});

async function create_docstatus_change_warning(updated_states) {
	return await new Promise((resolve) => {
		frappe.confirm(
			__(
				`DocStatus of the following states have changed:<br><strong>{0}</strong><br>
				Do you want to update the docstatus of existing documents in those states?<br>
				This does not undo any effect bought in by the document's existing docstatus.
				`,
				[updated_states.join(", ")]
			),
			() => resolve(true),
			() => resolve(false)
		);
	});
}
