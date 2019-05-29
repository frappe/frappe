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
	let nav_obj = {}, dropdown_nav_obj = {};
	nav_obj.changed = false;
	var {UP, DOWN, LEFT, RIGHT, ENTER, SPACE} = frappe.ui.keyCode;
	check_width_change(nav_obj);
	$(document).on('keydown.nav',(e)=> {
		if(!in_list([UP, DOWN, LEFT, RIGHT, ENTER, SPACE], e.which)) {
			return;
		}
		let $page = $(frappe.container.page);
		if($page.find('.modules-section').is(':visible')) {
			if ($('[role="listbox"]').is(":visible") || $('.dropdown-menu').is(':visible') 
				|| $('.modal').is(':visible') || $('input:focus').length > 0) {
					return;
			}
			if($page.find('.module-dropdown').is(':visible')) {
				navigate(e, dropdown_nav_obj,$page.find('.module-dropdown li').filter(':visible'), 'a', true);
			} else {
				navigate(e, nav_obj, $page.find('.module-box'), '.module-box-link', false);
			}
		}

	})
}

function navigate(e, nav_obj, $el, enter_el, is_dropdown) {
	if(e.which>=37 && e.which <=40) {
		navigate_directions(e, nav_obj, $el);
	}
	else {
		if(e.which === 13 && nav_obj.selected) {
			nav_enter(nav_obj,enter_el);
		}
		if(e.which === 32) {
			e.preventDefault();
			nav_space(nav_obj, is_dropdown);
		}
	}
}

function navigate_directions(e, nav_obj, $el) {
	if(!nav_obj.grid || nav_obj.changed) {
		nav_obj.position = { x: 0, y: 0 }
		populate_grid(nav_obj, $el);
		add_selected_class(nav_obj);
		nav_obj.changed = false;
	} else {
		if (e.which === 37) // left
			nav_left(nav_obj);
		else if (e.which === 38) // up
			nav_up(nav_obj);
		else if (e.which === 39) // right
			nav_right(nav_obj);
		else if (e.which === 40) // down
			nav_down(nav_obj);
		add_selected_class(nav_obj);
	}
}

function check_width_change(nav_obj) {
	$(document).on('change',()=> {		
		nav_obj.changed = true;
	})

	$(window).resize(() => {
		nav_obj.changed = true;
	});
}

function populate_grid(nav_obj, $el) {
	nav_obj.grid = [];
	let el_top = $el.eq(0).offset().top;
	let row_ar = [];
	$el.each(function (i,v) {
		if($(v).offset().top === el_top) {
			row_ar.push($(v));
		} else {
			el_top = $(v).offset().top;
			nav_obj.grid.push(row_ar);
			row_ar = [$(v)];
		}
		
	});
	nav_obj.grid.push(row_ar);
}


function nav_left(nav_obj) {
    nav_obj.position.x--;
    if (nav_obj.position.x < 0)
        nav_obj.position.x = 0;
}

function nav_up(nav_obj) {
	if(nav_obj.position.y > 0) {
		let init_pos = nav_obj.position.y;
		nav_obj.position.y--;
		while(!nav_obj.grid[nav_obj.position.y][nav_obj.position.x] && nav_obj.position.y > 0) {
			nav_obj.position.y--;
		}
		if(!nav_obj.grid[nav_obj.position.y][nav_obj.position.x]) nav_obj.position.y=init_pos;
	}
}

function nav_right(nav_obj) {
    nav_obj.position.x++;
    if (nav_obj.position.x >= nav_obj.grid[nav_obj.position.y].length)
		nav_obj.position.x = nav_obj.grid[nav_obj.position.y].length - 1;
}

function nav_down(nav_obj) {
	if(nav_obj.position.y < nav_obj.grid.length-1) {
		let init_pos = nav_obj.position.y;
		nav_obj.position.y++;
		while(!nav_obj.grid[nav_obj.position.y][nav_obj.position.x] && nav_obj.position.y < nav_obj.grid.length-1) {
			nav_obj.position.y++;
		}
		if(!nav_obj.grid[nav_obj.position.y][nav_obj.position.x]) nav_obj.position.y=init_pos;
	}
}

function add_selected_class(nav_obj) {
	if(nav_obj.selected) nav_obj.selected.removeClass('selected');
	nav_obj.selected = nav_obj.grid[nav_obj.position.y][nav_obj.position.x]
	nav_obj.selected.addClass('selected');
}

function nav_enter(nav_obj, $el) {
	window.location.href = nav_obj.selected.find($el).attr('href');
}

function nav_space(nav_obj, is_dropdown) {
	if(!is_dropdown) {
		if(nav_obj.selected) nav_obj.selected.find('.octicon-chevron-down').click();
	}
	else {
		$('body').click();
		if(nav_obj.selected) {
			reset_nav_obj(nav_obj);
		}
	}
}

function reset_nav_obj(nav_obj) {
	nav_obj.selected.removeClass('selected');
	nav_obj.grid = null;
	nav_obj.position = { x: 0, y: 0};
}

export {
	generate_route,
	keyboard_nav
};
