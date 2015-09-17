// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.is_starred = function(doc) {
	var starred = frappe.ui.get_starred_by(doc);
	return starred.indexOf(user)===-1 ? false : true;
}

frappe.ui.get_starred_by = function(doc) {
	var starred = doc._starred_by;
	if(starred) {
		starred = JSON.parse(starred);
	}

	return starred || [];
}

frappe.ui.toggle_star = function($btn, doctype, name) {
	var add = $btn.hasClass("not-starred") ? "Yes" : "No";
	frappe.call({
		method: "frappe.desk.star.toggle_star",
		quiet: true,
		args: {
			doctype: doctype,
			name: name,
			add: add,
		},
		callback: function(r) {
			if(!r.exc) {
				// update in all local-buttons
				var action_buttons = $('.star-action[data-name="'+ name.replace(/"/g, '\"')
					+'"][data-doctype="'+ doctype.replace(/"/g, '\"')+'"]');

				if(add==="Yes") {
					action_buttons.removeClass("not-starred").removeClass("text-extra-muted");
				} else {
					action_buttons.addClass("not-starred").addClass("text-extra-muted");
				}

				// update in locals (form)
				var doc = locals[doctype] && locals[doctype][name];
				if(doc) {
					var starred_by = JSON.parse(doc._starred_by || "[]"),
						idx = starred_by.indexOf(user);
					if(add==="Yes") {
						if(idx===-1)
							starred_by.push(user);
					} else {
						if(idx!==-1) {
							starred_by = starred_by.slice(0,idx).concat(starred_by.slice(idx+1))
						}
					}
					doc._starred_by = JSON.stringify(starred_by);
				}
			}
		}
	});
};
