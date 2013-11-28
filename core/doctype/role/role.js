// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

cur_frm.cscript.refresh = function(doc) {
	cur_frm.add_custom_button("Permission Manager", function() {
		wn.route_options = {"role": doc.name};
		wn.set_route("permission-manager");
	})
}
