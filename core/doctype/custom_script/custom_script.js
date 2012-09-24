cur_frm.cscript.refresh = function(doc, dt, dn) {
	if (doc.script_type == 'Server') {
		set_field_permlevel('script', 1);
		set_field_permlevel('dt', 1);
	}
}