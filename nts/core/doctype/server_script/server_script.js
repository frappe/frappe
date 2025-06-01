// Copyright (c) 2019, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Server Script", {
	setup: function (frm) {
		frm.trigger("setup_help");
	},
	refresh: function (frm) {
		if (frm.doc.script_type != "Scheduler Event") {
			frm.dashboard.hide();
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__("Compare Versions"), () => {
				new nts.ui.DiffView("Server Script", "script", frm.doc.name);
			});
		}

		frm.call("get_autocompletion_items")
			.then((r) => r.message)
			.then((items) => {
				frm.set_df_property("script", "autocompletions", items);
			});

		frm.trigger("check_safe_exec");
	},

	check_safe_exec(frm) {
		nts.xcall("nts.core.doctype.server_script.server_script.enabled").then((enabled) => {
			if (enabled === false) {
				let docs_link =
					"https://ntsframework.com/docs/user/en/desk/scripting/server-script";
				let docs = `<a href=${docs_link}>${__("Official Documentation")}</a>`;

				frm.dashboard.clear_comment();
				let msg = __("Server Scripts feature is not available on this site.") + " ";
				msg += __("To enable server scripts, read the {0}.", [docs]);
				frm.dashboard.add_comment(msg, "yellow", true);
			}
		});
	},

	setup_help(frm) {
		frm.get_field("help_html").html(`
<h4>DocType Event</h4>
<p>Add logic for standard doctype events like Before Insert, After Submit, etc.</p>
<pre>
	<code>
# set property
if "test" in doc.description:
	doc.status = 'Closed'


# validate
if "validate" in doc.description:
	raise nts.ValidationError

# auto create another document
if doc.allocated_to:
	nts.get_doc(dict(
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

if nts.form_dict.message == "ping":
	nts.response['message'] = "pong"
else:
	nts.response['message'] = "ok"
</code></pre>

<hr>

<h4>Permission Query</h4>
<p>Add conditions to the where clause of list queries.</p>
<pre><code>
# generate dynamic conditions and set it in the conditions variable
tenant_id = nts.db.get_value(...)
conditions = f'tenant_id = {tenant_id}'

# resulting select query
select name from \`tabPerson\`
where tenant_id = 2
order by creation desc
</code></pre>
`);
	},
});
