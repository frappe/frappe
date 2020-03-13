function generate_route(item) {
	const type = item.type.toLowerCase()
	if (type === "doctype") {
		item.doctype = item.name;
	}
	let route = "";
	if (!item.route) {
		if (item.link) {
			route = strip(item.link, "#");
		} else if (type === "doctype") {
			if (frappe.model.is_single(item.doctype)) {
				route = "Form/" + item.doctype;
			} else {
				if (item.filters) {
					frappe.route_options = item.filters;
				}
				route = "List/" + item.doctype;
			}
		} else if (type === "report" && item.is_query_report) {
			route = "query-report/" + item.name;
		} else if (type === "report") {
			route = "List/" + item.doctype + "/Report/" + item.name;
		} else if (type === "page") {
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

	// if(type==="page" || type==="help" || type==="report" ||
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

// function get_luminosity(color) {
// 	let c = color.substring(1);      // strip #
// 	let rgb = parseInt(c, 16);   // convert rrggbb to decimal
// 	let r = (rgb >> 16) & 0xff;  // extract red
// 	let g = (rgb >>  8) & 0xff;  // extract green
// 	let b = (rgb >>  0) & 0xff;  // extract blue

// 	let luma = 0.2126 * r + 0.7152 * g + 0.0722 * b; // per ITU-R BT.709

// 	return luma
// }

// function shadeColor(color, percent) {
//     var R = parseInt(color.substring(1,3),16);
//     var G = parseInt(color.substring(3,5),16);
//     var B = parseInt(color.substring(5,7),16);

//     R = parseInt(R * (100 + percent) / 100);
//     G = parseInt(G * (100 + percent) / 100);
//     B = parseInt(B * (100 + percent) / 100);

//     R = (R<255)?R:255;
//     G = (G<255)?G:255;
//     B = (B<255)?B:255;

//     var RR = ((R.toString(16).length==1)?"0"+R.toString(16):R.toString(16));
//     var GG = ((G.toString(16).length==1)?"0"+G.toString(16):G.toString(16));
//     var BB = ((B.toString(16).length==1)?"0"+B.toString(16):B.toString(16));

//     return "#"+RR+GG+BB;
// }

export { generate_route, generate_grid };