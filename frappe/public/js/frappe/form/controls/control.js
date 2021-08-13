import './base_control';
import './base_input';
import './data';
import './int';
import './float';
import './currency';
import './date';
import './time';
import './datetime';
import './date_range';
import './select';
import './link';
import './dynamic_link';
import './text';
import './code';
import './text_editor';
import './comment';
import './check';
import './image';
import './attach';
import './attach_image';
import './table';
import './color';
import './signature';
import './password';
import './read_only';
import './button';
import './html';
import './markdown_editor';
import './html_editor';
import './heading';
import './autocomplete';
import './barcode';
import './geolocation';
import './multiselect';
import './multicheck';
import './table_multiselect';
import './multiselect_pills';
import './multiselect_list';
import './rating';
import './duration';
import './icon';

frappe.ui.form.make_control = function (opts) {
	var control_class_name = "Control" + opts.df.fieldtype.replace(/ /g, "");
	if(frappe.ui.form[control_class_name]) {
		return new frappe.ui.form[control_class_name](opts);
	} else {
		// eslint-disable-next-line
		console.log("Invalid Control Name: " + opts.df.fieldtype);
	}
};

