frappe.set_dark_mode = function() {
	document.cookie = "DarkMode=True";
};

frappe.dark_mode = function(){
	if(frappe.get_cookie("DarkMode")){
		frappe.set_css();
	}
	else{
		frappe.remove_css();
	}
};

frappe.set_css = function(){
    var css = "*{
        "color": white !important;
    }";
}

frappe.remove_css = function(){
    console.log("remove_css");
}