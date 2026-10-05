// Injected into header/footer pages so clone_and_update is available
// when browser.py calls header_page.evaluate("clone_and_update(...)").
// Matches print_designer/print_designer/page/print_designer/update_page_no.js

const replaceText = (parentEL, className, text) => {
	const elements = parentEL.getElementsByClassName(className);
	for (let j = 0; j < elements.length; j++) {
		elements[j].textContent = text;
	}
};

const update_page_no = (clone, i, no_of_pages, print_designer) => {
	const dateObj = new Date();
	if (print_designer) {
		replaceText(clone, "page_info_page", i);
		replaceText(clone, "page_info_topage", no_of_pages);
		replaceText(clone, "page_info_date", dateObj.toLocaleDateString());
		replaceText(clone, "page_info_isodate", dateObj.toISOString());
		replaceText(clone, "page_info_time", dateObj.toLocaleTimeString());
	} else {
		replaceText(clone, "page", i);
		replaceText(clone, "topage", no_of_pages);
		replaceText(clone, "date", dateObj.toLocaleDateString());
		replaceText(clone, "isodate", dateObj.toISOString());
		replaceText(clone, "time", dateObj.toLocaleTimeString());
	}
};

const toggle_visibility = (clone, id, visibility) => {
	const element = clone.querySelector(id);
	if (element) {
		element.style.display = visibility;
	}
};

const add_wrapper = (clone, wrapper) => {
	wrapper = wrapper.cloneNode(true);
	wrapper.appendChild(clone);
	return wrapper;
};

const extract_elements = (template, type) => {
	const extracted = {
		even: template.querySelector(`#evenPage${type}`).cloneNode(true),
		odd: template.querySelector(`#oddPage${type}`).cloneNode(true),
		last: template.querySelector(`#lastPage${type}`).cloneNode(true),
	};

	extracted.even.style.display = "block";
	extracted.odd.style.display = "block";
	extracted.last.style.display = "block";

	template.querySelector(`#evenPage${type}`).remove();
	template.querySelector(`#oddPage${type}`).remove();
	template.querySelector(`#lastPage${type}`).remove();

	template.querySelector(`#firstPage${type}`).style.display = "none";
	extracted.even = add_wrapper(extracted.even, template);
	extracted.odd = add_wrapper(extracted.odd, template);
	extracted.last = add_wrapper(extracted.last, template);
	template.querySelector(`#firstPage${type}`).style.display = "block";

	return extracted;
};

const clone_and_update = (
	selector,
	no_of_pages,
	print_designer,
	type = null,
	is_dynamic = true
) => {
	const template = document.querySelector(selector);
	if (!template) return;
	let elements;
	if (print_designer) {
		elements = extract_elements(template, type);
	}
	const fragment = document.createDocumentFragment();
	for (let i = 2; i <= (is_dynamic ? no_of_pages : 4); i++) {
		let clone;
		if (print_designer) {
			if (i == (is_dynamic ? no_of_pages : 4)) {
				clone = elements.last?.cloneNode(true);
			} else if (i % 2 == 0) {
				clone = elements.even?.cloneNode(true);
			} else {
				clone = elements.odd?.cloneNode(true);
			}
		} else {
			clone = template.cloneNode(true);
		}
		if (is_dynamic) {
			update_page_no(clone, i, no_of_pages, print_designer);
		}
		fragment.appendChild(clone);
	}
	template.parentElement.appendChild(fragment);
	if (is_dynamic) {
		update_page_no(template, 1, no_of_pages, print_designer);
	}
};
