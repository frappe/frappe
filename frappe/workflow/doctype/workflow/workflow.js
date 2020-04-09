frappe.provide("frappe.core")

frappe.ui.form.on("Workflow", {
	onload: function(frm) {
		frm.set_query("document_type", {"issingle": 0, "istable": 0});
	},
	refresh: function(frm) {
		frm.events.update_field_options(frm);
		frm.ignore_warning = false;
	},
	validate: (frm) => {
		if (frm.ignore_warning) return;
		let states_list = [];
		frm.doc.states.map(state=> states_list.push(state.state));
		return frappe.xcall(
			'frappe.workflow.doctype.workflow.workflow.get_workflow_state_count',
			{
				doctype: frm.doc.document_type,
				workflow_state_field: frm.doc.workflow_state_field,
				states: states_list
			}).then(result => {
				if (result && result.length) {
					frappe.validated = false;
					frm.states = result;
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
		frm.warning_dialog = new frappe.ui.Dialog({
			title: __(`Worflow States Don't Exist`),
			indicator: 'red',
			fields: [
				{
					fieldname: 'warning_text',
					label: __('Warning'),
					fieldtype: 'HTML',
				},
				{
					fieldname: 'state_table',
					label: __('Count of existing Document States'),
					fieldtype: 'HTML',
				},
			],
			primary_action_label: __(`Don't Save`),
			primary_action: () => {
				frm.warning_dialog.hide();
			},
		});
		frm.warning_dialog.get_close_btn().hide();

		frm.warning_dialog.get_field('warning_text').$wrapper.html(
			`<p>
				${__(`There are documents which have workflow states that do not exist in this Workflow.
				It is recommended that you add these states to the Workflow and change their states
				before removing these states.`)}
			</p>`
		)
		frm.trigger('render_state_table');
		frm.trigger('render_dismiss_button');
		frm.warning_dialog.show();
	},
	render_state_table: function(frm) {
		let wrapper = frm.warning_dialog.get_field('state_table').$wrapper;
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

		$(`<table class="table table-bordered" style="margin:0px; width: 50%">
			<thead>
				<tr class="text-muted">
					<th>${__('State')}</th>
					<th>${__('Count')}</th>
				</tr>
			</thead>
			<tbody>
				${rows}
			</tbody>
		</table>`).appendTo(wrapper);
	},
	render_dismiss_button: function(frm) {
		frm.warning_dialog.header.find('.buttons').prepend(
			`<button type="button" class="btn dismiss btn-danger btn-sm">${__('Dismiss')}</button>`
		);

		frm.warning_dialog.$wrapper.find('.dismiss').on('click', () => {
			frm.warning_dialog.hide();
			frm.ignore_warning = true;
			frm.save();
		});
	}

});

