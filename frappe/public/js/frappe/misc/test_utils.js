// for testing
frappe.click_button = function(text, idx) {
	let container = '';
	if(typeof idx === 'string') {
		container = idx + ' ';
		idx = 0;
	}
	let element = $(`${container}.btn:contains("${text}"):visible`);
	if(!element.length) {
		throw `did not find any button containing ${text}`;
	}
	element.get(idx || 0).click();
	return frappe.timeout(0.5);
};

frappe.click_link = function(text, idx) {
	let element = $(`a:contains("${text}"):visible`);
	if(!element.length) {
		throw `did not find any link containing ${text}`;
	}
	element.get(idx || 0).click();
	return frappe.timeout(0.5);
};

frappe.click_element = function(selector, idx) {
	// Selector by class name like $(`.cart-items`)
	let element = $(`${selector}`);
	if(!element.length) {
		throw `did not find any link containing ${selector}`;
	}
	element.get(idx || 0).click();
	return frappe.timeout(0.5);
};

frappe.set_control= function(fieldname, value) {
	let control = $(`.form-control[data-fieldname="${fieldname}"]:visible`);
	if(!control.length) {
		throw `did not find any control with fieldname ${fieldname}`;
	}
	control.val(value).trigger('change');
	return frappe.timeout(0.5);
};

frappe.click_check = function(label, idx) {
	let check = $(`.checkbox:contains("${label}") input`);
	if(!check.length) {
		throw `did not find any checkbox with label ${label}`;
	}
	check.get(idx || 0).click();
	return frappe.timeout(0.5);
};