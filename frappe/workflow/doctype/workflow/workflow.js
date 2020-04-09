frappe.provide("frappe.core")

frappe.ui.form.on("Workflow", {
	onload: function(frm) {
		frm.set_query("document_type", {"issingle": 0, "istable": 0});
	},
	refresh: function(frm) {
		frm.events.update_field_options(frm);
		frm.ignore_warning = false;
	},
	onload_post_render: function(frm) {
		frm.trigger('get_orphaned_states_and_count').then(()=> {
			frm.trigger('render_state_table');
		});
	},
	validate: (frm) => {
		if (frm.ignore_warning) return;
		return frm.trigger('get_orphaned_states_and_count').then(()=> {
				frappe.validated = false;
				frm.trigger('create_warning_dialog');
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
		}

		frappe.warn(__(`Worflow States Don't Exist`), message_html, proceed_action, __(`Save Anyway`));
	},
	set_table_html: function(frm) {
		let rows = frm.states.map(r => {
			let indicator_color_map = {
				'0': 'red',
				'1': 'green',
				'2': 'darkgrey'
			}
			return `<tr>
				<td>
					<div class="indicator ${indicator_color_map[r.docstatus]}">
						${r[frm.doc.workflow_state_field]}
					</div>
				</td>
				<td>${r.count}</td></tr>
			`;
		}).join('');

		frm.state_table_html = (`<table class="table table-bordered" style="margin:0px; width: 50%">
			<thead>
				<tr class="text-muted">
					<th>${__('State')}</th>
					<th>${__('Count')}</th>
				</tr>
			</thead>
			<tbody>
				${rows}
			</tbody>
		</table>`);
	},
	get_orphaned_states_and_count: function(frm) {
		let states_list = [];
		frm.doc.states.map(state=> states_list.push(state.state));
		return frappe.xcall('frappe.workflow.doctype.workflow.workflow.get_workflow_state_count',{
			doctype: frm.doc.document_type,
			workflow_state_field: frm.doc.workflow_state_field,
			states: states_list
		}).then(result => {
			if (result && result.length) {
				frm.states = result;
				frm.trigger('set_table_html');
			}
		});
	},
	render_state_table: function(frm) {
		const $wrapper = frm.get_field('states').$wrapper;
		const label_html =
			`<p class="text-muted small" style="margin-top: 30px">
				${'Document States that do not exist in your Workflow'}
			</p>`;
		$(label_html + frm.state_table_html).insertAfter($wrapper);
	}
});

