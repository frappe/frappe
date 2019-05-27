function generate_route(item) {
	if(item.type==="doctype") {
		item.doctype = item.name;
	}
	let route = '';
	if(!item.route) {
		if(item.link) {
			route=strip(item.link, "#");
		} else if(item.type==="doctype") {
			if(frappe.model.is_single(item.doctype)) {
				route = 'Form/' + item.doctype;
			} else {
				if (item.filters) {
					frappe.route_options=item.filters;
				}
				route="List/" + item.doctype;
			}
		} else if(item.type==="report" && item.is_query_report) {
			route="query-report/" + item.name;
		} else if(item.type==="report") {
			route="List/" + item.doctype + "/Report/" + item.name;
		} else if(item.type==="page") {
			route=item.name;
		}

		route = '#' + route;
	} else {
		route = item.route;
	}

	if(item.route_options) {
		route += "?" + $.map(item.route_options, function(value, key) {
			return encodeURIComponent(key) + "=" + encodeURIComponent(value); }).join('&');
	}

	// if(item.type==="page" || item.type==="help" || item.type==="report" ||
	// (item.doctype && frappe.model.can_read(item.doctype))) {
	//     item.shown = true;
	// }
	return route;
}

function keyboard_nav() {
	let mod_nav_obj = {}, dropdown_nav_obj = {};
	$(document).on('keydown.nav',(e)=> {

		if($('.modules-section').is(':visible')) {
			if ($('[role="listbox"]').is(":visible") || $('.dropdown-menu').is(':visible') 
				|| $('.modal').is(':visible') || $('input:focus').length > 0) {
					return;
			} 
			if($('.module-dropdown').is(':visible')) {
				if(!dropdown_nav_obj.li || !dropdown_nav_obj.li.is(':visible')) {
					dropdown_nav_obj.li = $('.module-dropdown li').filter(':visible');
					dropdown_nav_obj.liSelected = null;
				}
				object_nav(e, true, dropdown_nav_obj,'a');
			} else {
				let $section_list = $('.modules-section');
				if(e.which === 77) {
					add_selected_class(mod_nav_obj, $section_list, 0);
				} else if(e.which === 68) {
					add_selected_class(mod_nav_obj, $section_list, 1);
				} else if(e.which === 80) {
					add_selected_class(mod_nav_obj, $section_list, 2);
				} else if(e.which === 65) {
					add_selected_class(mod_nav_obj, $section_list, 3);
				}
				else {
					object_nav(e, false, mod_nav_obj, $('.module-box-link'));
				}
			}
		}

	})
}

function object_nav(e, is_dropdown, nav_obj, enter_el) {
	if(e.which === 40 && nav_obj.li){
		nav(true, nav_obj);
	} else if(e.which === 38 && nav_obj.li) {
		nav(false, nav_obj)
	} else if(e.which === 13 && nav_obj.liSelected && enter_el) {
		window.location.href = nav_obj.liSelected.find(enter_el).attr('href');
		reset_nav_obj(nav_obj);
	} else if(e.which === 32) {
		e.preventDefault();
		if(!is_dropdown) {
			if(nav_obj.liSelected) nav_obj.liSelected.find('.octicon-chevron-down').click();
		}
		else {
			$('body').click();
			if(nav_obj.liSelected) {
				reset_nav_obj(nav_obj);
			}
		}
	}
}

function reset_nav_obj(nav_obj) {
	nav_obj.liSelected.removeClass('selected');
	nav_obj.li=null;
	nav_obj.liSelected=null;
}

function nav(is_down, nav_obj) {
	if(nav_obj.liSelected){
		nav_obj.liSelected.removeClass('selected');
		nav_obj.next = is_down ? nav_obj.liSelected.next(): nav_obj.liSelected.prev();
		if(nav_obj.next.length > 0){
			nav_obj.liSelected = nav_obj.next.addClass('selected');
		}else{
			nav_obj.liSelected = nav_obj.li.eq(0).addClass('selected');
		}
	}else{
		nav_obj.liSelected = is_down ? nav_obj.li.eq(0).addClass('selected') : nav_obj.li.last().addClass('selected');
	}
}

function add_selected_class(obj, $section_list, index) {
	obj.li = $section_list.eq(index).find('.module-box');
	if(obj.liSelected) obj.liSelected.removeClass('selected');
	obj.liSelected = obj.li.eq(0);
	obj.liSelected.addClass('selected');
}

export {
	generate_route,
	keyboard_nav
};
