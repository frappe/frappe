frappe.ui.form.on("Website Group", "refresh", function(frm) {
	if (!frm.doc.__islocal) {
		cur_frm.set_intro(__("Published on website at: {0}",
			[repl('<a href="/%(website_route)s" target="_blank">/%(website_route)s</a>',
				frm.doc.__onload)]));
	}
})
