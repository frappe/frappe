frappe.set_dark_mode = function() {
    var date = new Date;
    date.setDate(date.getDate() + 180);
    if(frappe.get_cookie("dark_mode") == "True" || frappe.get_cookie("dark_mode") == undefined){
        document.cookie = "dark_mode=False; expires="+ date +"";
        frappe.dark_mode();
    }
    else{
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