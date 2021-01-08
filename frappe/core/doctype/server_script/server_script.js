// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Server Script', {
	setup: function(frm) {
		frm.trigger('setup_help');
	},
	refresh: function(frm) {
		if (frm.doc.script_type === 'Scheduler Event' && !frm.doc.disabled) {
			frm.add_custom_button('Schedule Script', function() {
				var d = new frappe.ui.Dialog({
					title: "Schedule Script Execution",
					fields: [
						{
							fieldname: "event_type",
							label: __('Select Event Type'),
							fieldtype: "Select",
							options: "All\nHourly\nDaily\nWeekly\nMonthly\nYearly\nHourly Long\nDaily Long\nWeekly Long\nMonthly Long"
						},
					],
					primary_action_label: __('Schedule Script'),
					primary_action: () => {
						d.get_primary_btn().attr('disabled', true);
						var data = d.get_values();
						d.hide();
						if(data) {
							frm.events.schedule_script(frm, data);
						}

					}
				});

				d.show();

			});
		}
	},

	schedule_script(frm, data) {
		frm.call({
			method: "frappe.core.doctype.server_script.server_script.setup_scheduler_events",
			args: {
				'script_name': frm.doc.name,
				'frequency': data.event_type
			}
		});
	},

	setup_help(frm) {
		frm.get_field('help_html').html(`
<h4>DocType Event</h4>
<p>Add logic for standard doctype events like Before Insert, After Submit, etc.</p>
<pre>
	<code>
# set property
if "test" in doc.description:
	doc.status = 'Closed'


# validate
if "validate" in doc.description:
	raise frappe.ValidationError

# auto create another document
if doc.allocated_to:
	frappe.get_doc(dict(
		doctype = 'ToDo'
		owner = doc.allocated_to,
		description = doc.subject
	)).insert()
</code>
</pre>

<hr>

<h4>API Call</h4>
<p>Respond to <code>/api/method/&lt;method-name&gt;</code> calls, just like whitelisted methods</p>
<pre><code>
# respond to API

if frappe.form_dict.message == "ping":
	frappe.response['message'] = "pong"
else:
	frappe.response['message'] = "ok"
</code></pre>

<hr>

<h4>Permission Query</h4>
<p>Add conditions to the where clause of list queries.</p>
<pre><code>
# generate dynamic conditions and set it in the conditions variable
tenant_id = frappe.db.get_value(...)
conditions = 'tenant_id = {}'.format(tenant_id)

# resulting select query
select name from \`tabPerson\`
where tenant_id = 2
order by creation desc
</code></pre>
`);
	}

});
