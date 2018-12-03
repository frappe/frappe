frappe.dark_mode = {
	set_mode: function() {
		var date = new Date;
		date.setDate(date.getDate() + 180);
		if(frappe.get_cookie("dark_mode") == undefined) {	//  Dark Mode is undefined, Set it to Off
			document.cookie = "dark_mode=False; expires="+ date +"";
		}
		frappe.dark_mode.check_mode();
	},

	toggle_mode: function(){
		var date = new Date;
		date.setDate(date.getDate() + 180);
		if(frappe.get_cookie("dark_mode") == "True") {	//  Dark Mode is On, Set it to Off
			document.cookie = "dark_mode=False; expires="+ date +"";
		} else {	//  Dark Mode is Off, Set it to On
			document.cookie = "dark_mode=True; expires="+ date +"";
		}
		frappe.dark_mode.check_mode();
	},

	check_mode: function(){
		var StyleSheets = document.styleSheets;
		var StyleSheet;
		if(frappe.get_cookie("dark_mode") == "False") {
			for (StyleSheet in StyleSheets) {
				if (StyleSheets[StyleSheet].href.indexOf("desk-dark") != -1) {
					StyleSheets[StyleSheet].disabled = true;
					$('#dark_mode').prop('checked', false);
					frappe.set_route(frappe.get_route_str());
					break;
				}
			}
		} else {
			for (StyleSheet in StyleSheets) {
				if (StyleSheets[StyleSheet].href.indexOf("desk-dark") != -1) {
					StyleSheets[StyleSheet].disabled = false;
					$('#dark_mode').prop('checked', true);
					frappe.set_route(frappe.get_route_str());
					break;
				}
			}
		}
	}
};