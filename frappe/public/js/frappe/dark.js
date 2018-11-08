frappe.set_dark_mode = function() {
    if(frappe.get_cookie("DarkMode") == "True" || frappe.get_cookie("DarkMode") == undefined){
        document.cookie = "DarkMode=False";
        frappe.dark_mode();
    }
    else{
        document.cookie = "DarkMode=True";
        frappe.dark_mode();
    }
};

frappe.dark_mode = function(){
	if(frappe.get_cookie("DarkMode") == "False"){
		var styleSheets = document.styleSheets;
        for (var i = 0; i < styleSheets.length; i++) {
            if (styleSheets[i].href.indexOf("dark.css") != -1) {
                styleSheets[i].disabled = true;
                break;
            }
        }
    }
    else{
        var styleSheets = document.styleSheets;
        for (var i = 0; i < styleSheets.length; i++) {
            if (styleSheets[i].href.indexOf("dark.css") != -1) {
                styleSheets[i].disabled = false;
                break;
            }
        }
    }
};