frappe.dark_mode = {
	set_mode: function() {
		var date = new Date;
		date.setDate(date.getDate() + 180);
		if(frappe.get_cookie("dark_mode") == undefined){	//  Dark Mode is undefined, Set it to Off
			document.cookie = "dark_mode=False; expires="+ date +"";
			frappe.dark_mode.check_mode();
		}
		else{	//  Dark Mode is defined, Check
			frappe.dark_mode.check_mode();
		}
	},

	toggle_mode: function(){
		var date = new Date;
		date.setDate(date.getDate() + 180);
		if(frappe.get_cookie("dark_mode") == "True"){	//  Dark Mode is On, Set it to Off
			document.cookie = "dark_mode=False; expires="+ date +"";
			frappe.dark_mode.check_mode();
		}
		else{	//  Dark Mode is Off, Set it to On
			document.cookie = "dark_mode=True; expires="+ date +"";
			frappe.dark_mode.check_mode();
		}
	},

	check_mode: function(){
		if(frappe.get_cookie("dark_mode") == "False"){
			var styleSheets = document.styleSheets;
			for (var i = 0; i < styleSheets.length; i++) {
				if (styleSheets[i].href.indexOf("desk_dark.css") != -1) {
					styleSheets[i].disabled = true;
					$('#dark_mode').prop('checked', false);
					break;
				}
			}
		}
		else{
			var styleSheets = document.styleSheets;
			for (var i = 0; i < styleSheets.length; i++) {
				if (styleSheets[i].href.indexOf("desk_dark.css") != -1) {
					$('#dark_mode').prop('checked', true);
					styleSheets[i].disabled = false;
					break;
				}
			}
		}
	}
}