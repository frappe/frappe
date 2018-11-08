frappe.set_dark_mode = function() {
	var date = new Date;
	date.setDate(date.getDate() + 180);
	if(frappe.get_cookie("dark_mode") == "True" || frappe.get_cookie("dark_mode") == undefined){	//  If Dark Mode is On or If Dark Mode is undefined, Set it to Off
		document.cookie = "dark_mode=False; expires="+ date +"";
		frappe.dark_mode();
	}
	else{	//  If Dark Mode is Off, Set it to On
		document.cookie = "dark_mode=True; expires="+ date +"";
		frappe.dark_mode();
	}
};

frappe.dark_mode = function(){
	if(frappe.get_cookie("dark_mode") == "False"){
		var styleSheets = document.styleSheets;
		for (var i = 0; i < styleSheets.length; i++) {
			if (styleSheets[i].href.indexOf("dark.css") != -1) {
				styleSheets[i].disabled = true;
				$('#dark_mode').prop('checked', false);
				break;
			}
		}
	}
	else{
		var styleSheets = document.styleSheets;
		for (var i = 0; i < styleSheets.length; i++) {
			if (styleSheets[i].href.indexOf("dark.css") != -1) {
				$('#dark_mode').prop('checked', true);
				styleSheets[i].disabled = false;
				break;
			}
		}
	}
};