
To trigger an event when a row from a grid has been deleted, you need to add a handler the `fieldname_remove` event, where fieldname is the fieldname of the grid (Table)

<h3>Example for add</h3>

<p>Recalculate totals when a Journal Entry row has been added</p>

	frappe.ui.form.on("Journal Entry Account", "accounts_add", function(frm){
    		cur_frm.cscript.update_totals(frm.doc);
	});

<!-- markdown -->

<h3>Example for delete</h3>

<p>Recalculate totals when a Journal Entry row has been deleted</p>

	frappe.ui.form.on("Journal Entry Account", "accounts_remove", function(frm){
    		cur_frm.cscript.update_totals(frm.doc);
	});

<!-- markdown -->