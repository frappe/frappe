// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Submission Queue', {
    refresh: function(frm) {
      frm.add_custom_button(__("Unlock"), () => {
		frm.call("unlock_doc")
	  })
  }
});
