frappe.provide("frappe.core")

frappe.ui.form.on("Workflow", {
	onload: function(frm) {
		frm.set_query("document_type", {"issingle": 0, "istable": 0});
	},
	refresh: function(frm) {
		if (frm.doc.document_type) {
			frm.add_custom_button(__('Go to {0} List', [frm.doc.document_type]), () => {
				frappe.set_route('List', frm.doc.document_type);
			});
		}

		frm.events.update_field_options(frm);
		frm.ignore_warning = frm.is_new() ? true : false;

		if (frm.is_new()) {
			return;
		}

		frm.states = null;
		frm.trigger('make_state_table');
		frm.trigger('get_orphaned_states_and_count').then(() => {
			frm.trigger('render_state_table');
		});
	},
	validate: (frm) => {
		if (frm.ignore_warning) {
			return;
		}
		return frm.trigger('get_orphaned_states_and_count').then(() => {
			if (frm.states && frm.states.length) {
				frappe.validated = false;
				frm.trigger('create_warning_dialog');
			}
		});
	},
	document_type: function(frm) {
		frm.events.update_field_options(frm);
	},
	update_field_options: function(frm) {
		var doc = frm.doc;
		if (doc.document_type) {
			const get_field_method = 'frappe.workflow.doctype.workflow.workflow.get_fieldnames_for';
			frappe.xcall(get_field_method, { doctype: doc.document_type })
				.then(resp => {
					frappe.meta.get_docfield("Workflow Document State", "update_field", frm.doc.name).options = [""].concat(resp);
				})
		}
	},
	create_warning_dialog: function(frm) {
		const warning_html =
			`<p class="bold">
				${__('Are you sure you want to save this document?')}
			</p>
			<p>${__(`There are documents which have workflow states that do not exist in this Workflow.
				It is recommended that you add these states to the Workflow and change their states
				before removing these states.`)}
			</p>`;
		const message_html = warning_html + frm.state_table_html;
		let proceed_action = () => {
			frm.ignore_warning = true;
			frm.save();
		};

		frappe.warn(__(`Worflow States Don't Exist`), message_html, proceed_action, __(`Save Anyway`));
	},
	set_table_html: function(frm) {

		const promises = frm.states.map(r => {
			const state = r[frm.doc.workflow_state_field];
			return frappe.utils.get_indicator_color(state).then(color => {
				return `<tr>
				<td>
					<div class="indicator ${color}">
						<a class="text-muted orphaned-state">${r[frm.doc.workflow_state_field]}</a>
					</div>
				</td>
				<td>${r.count}</td></tr>`;
			});
		});

		Promise.all(promises).then(rows => {
			const rows_html = rows.join('');
			frm.state_table_html = (`<table class="table state-table table-bordered" style="margin:0px; width: 65%">
				<thead style="font-size: 12px">
					<tr class="text-muted">
						<th>${__('State')}</th>
						<th>${__('Count')}</th>
					</tr>
				</thead>
				<tbody>
					${rows_html}
				</tbody>
			</table>`);
		});
	},
	get_orphaned_states_and_count: function(frm) {
		if (frm.is_new()) return;
		let states_list = [];
		frm.doc.states.map(state => states_list.push(state.state));
		return frappe.xcall('frappe.workflow.doctype.workflow.workflow.get_workflow_state_count', {
			doctype: frm.doc.document_type,
			workflow_state_field: frm.doc.workflow_state_field,
			states: states_list
		}).then(result => {
			if (result && result.length) {
				frm.states = result;
				return frm.trigger('set_table_html');
			}
		});
	},
	make_state_table: function(frm) {
		const wrapper = frm.get_field('states').$wrapper;
		if (frm.state_table) {
			frm.state_table.empty();
		}
		frm.state_table = $(`<div class="state-table"><div>`).insertAfter(wrapper);
	},
	render_state_table: function(frm) {
		if (frm.states && frm.states.length) {
			const form_state_table_html =
				`<p class="text-muted small" style="margin-top: 30px">
					${'Document States that do not exist in your Workflow'}
				</p>
				${frm.state_table_html}
				</div>`;
			frm.state_table.html(form_state_table_html);

			$(frm.state_table).find('a.orphaned-state').on('click', (e) => {
				const state = $(e.currentTarget).text();
				let filters = {};
				filters[frm.doc.workflow_state_field] = state;
				frappe.set_route('List', frm.doc.document_type, filters);
			});
		}
	}

});

frappe.ui.form.on("Workflow Document State", {
	states_remove: function(frm) {
		frm.trigger('get_orphaned_states_and_count').then(() => {
			frm.trigger('render_state_table');
		});
	}
});

