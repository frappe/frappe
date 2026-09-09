import "./base_control";
import "./base_input";
import "./data";
import "./int";
import "./float";
import "./percent";
import "./currency";
import "./date";
import "./time";
import "./datetime";
import "./date_range";
import "./select";
import "./link";
import "./dynamic_link";
import "./link_combobox";
import "./dynamic_link_combobox";
import "./text";
import "./code";
import "./text_editor";
import "./comment";
import "./check";
import "./switch";
import "./image";
import "./attach";
import "./attach_image";
import "./table";
import "./color";
import "./signature";
import "./password";
import "./button";
import "./html";
import "./attachment_gallery";
import "./markdown_editor";
import "./html_editor";
import "./heading";
import "./autocomplete";
import "./autocomplete_combobox";
import "./barcode";
import "./geolocation";
import "./multiselect";
import "./multicheck";
import "./table_multiselect";
import "./multiselect_pills";
import "./multiselect_list";
import "./rating";
import "./duration";
import "./icon";
import "./phone";
import "./json";

// fieldtypes that have a combobox-backed variant behind the
// "Enable Combobox Link Field" system setting
const COMBOBOX_FIELDTYPES = new Set(["Link", "Dynamic Link", "Autocomplete"]);

frappe.ui.form.make_control = function (opts) {
	var control_class_name = "Control" + opts.df.fieldtype.replace(/ /g, "");
	if (COMBOBOX_FIELDTYPES.has(opts.df.fieldtype) && frappe.ui.form.is_combobox_link_enabled()) {
		control_class_name += "Combobox";
	}
	if (frappe.ui.form[control_class_name]) {
		return new frappe.ui.form[control_class_name](opts);
	} else {
		console.log("Invalid Control Name: " + opts.df.fieldtype);
	}
};
