cur_frm.cscript.refresh = function(doc, dt, dn) {
	if (doc.script_type == 'Server') {
		cur_frm.set_df_property('script', 'read_only', 1);
		cur_frm.set_df_property('dt', 'read_only', 1);
	}
}