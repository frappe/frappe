function generate_route(item) {
	if (item.type === "doctype") {
		item.doctype = item.name;
	}
	let route = "";
	if (!item.route) {
		if (item.link) {
			route = strip(item.link, "#");
		} else if (item.type === "doctype") {
			if (frappe.model.is_single(item.doctype)) {
				route = "Form/" + item.doctype;
			} else {
				if (item.filters) {
					frappe.route_options = item.filters;
				}
				route = "List/" + item.doctype;
			}
		} else if (item.type === "report" && item.is_query_report) {
			route = "query-report/" + item.name;
		} else if (item.type === "report") {
			route = "List/" + item.doctype + "/Report/" + item.name;
		} else if (item.type === "page") {
			route = item.name;
		}

		route = "#" + route;
	} else {
		route = item.route;
	}

	if (item.route_options) {
		route +=
			"?" +
			$.map(item.route_options, function(value, key) {
				return (
					encodeURIComponent(key) + "=" + encodeURIComponent(value)
				);
			}).join("&");
	}

	// if(item.type==="page" || item.type==="help" || item.type==="report" ||
	// (item.doctype && frappe.model.can_read(item.doctype))) {
	//     item.shown = true;
	// }
	return route;
}

function generate_grid(data) {
	function add(a, b) {
		return a + b;
	}

	const grid_max_cols = 6

	// Split the data into multiple arrays
	// Each array will contain grid elements of one row
	let processed = []
	let temp = []
	let init = 0
	data.forEach((data) => {
		init = init + data.columns;
		if (init > grid_max_cols) {
			init = data.columns
			processed.push(temp)
			temp = []
		}
		temp.push(data)
	})

	processed.push(temp)

	let grid_template = [];

	processed.forEach((data, index) => {
		let aa = data.map(dd => {
			return Array.apply(null, Array(dd.columns)).map(String.prototype.valueOf, dd.name)
		}).flat()

		if (aa.length < grid_max_cols) {
			let diff = grid_max_cols - aa.length;
			for (let ii = 0; ii < diff; ii++) {
				aa.push(`grid-${index}-${ii}`)
			}
		}

		grid_template.push(aa.join(" "))
	})
	let grid_template_area = ""

	grid_template.forEach(temp => {
		grid_template_area += `"${temp}" `
	})

	return grid_template_area
}

export { generate_route, generate_grid };