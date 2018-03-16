// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Transaction Log', {
	"formatter":function (row, cell, value, columnDef, dataContext, default_formatter) {
        value = default_formatter(row, cell, value, columnDef, dataContext);
       if (columnDef.id == "Chain Integrity" && dataContext["chain_integrity"] == "True") {
            value = "<span style='color:green!important;'>" + value + "</span>";
       }
       if (columnDef.id == "Chain Integrity" && dataContext["chain_integrity"] == "False") {
            value = "<span style='color:red!important;'>" + value + "</span>";
       }
       return value;
    }
});
