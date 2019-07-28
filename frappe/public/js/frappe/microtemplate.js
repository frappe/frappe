// Simple JavaScript Templating
// Adapted from John Resig - http://ejohn.org/ - MIT Licensed

frappe.template = {compiled: {}, debug:{}};
frappe.template.compile = function(str, name) {
	var key = name || str;

	if(!frappe.template.compiled[key]) {
		if(str.indexOf("'")!==-1) {
			str.replace(/'/g, "\\'");
			//console.warn("Warning: Single quotes (') may not work in templates");
		}

		// replace jinja style tags
		str = str.replace(/{{/g, "{%=").replace(/}}/g, "%}");

		// {% if not test %} --> {% if (!test) { %}
		str = str.replace(/{%\s?if\s?\s?not\s?([^\(][^%{]+)\s?%}/g, "{% if (! $1) { %}")

		// {% if test %} --> {% if (test) { %}
		str = str.replace(/{%\s?if\s?([^\(][^%{]+)\s?%}/g, "{% if ($1) { %}");

		// {% for item in list %}
		//       --> {% for (var i=0, len=list.length; i<len; i++) {  var item = list[i]; %}
		function replacer(match, p1, p2, offset, string) {
			var i = frappe.utils.get_random(3);
			var len = frappe.utils.get_random(3);
			return "{% for (var "+i+"=0, "+len+"="+p2+".length; "+i+"<"+len+"; "+i+"++) { var "
				+p1+" = "+p2+"["+i+"]; "+p1+"._index = "+i+"; %}";
		}
		str = str.replace(/{%\s?for\s([a-z._]+)\sin\s([a-z._]+)\s?%}/g, replacer);

		// {% endfor %} --> {% } %}
		str = str.replace(/{%\s?endif\s?%}/g, "{% }; %}");

		// {% else %} --> {% } else { %}
		str = str.replace(/{%\s?else\s?%}/g, "{% } else { %}");

		// {% endif %} --> {% } %}
		str = str.replace(/{%\s?endfor\s?%}/g, "{% }; %}");

		var fn_str = "var _p=[],print=function(){_p.push.apply(_p,arguments)};" +

	        // Introduce the data as local variables using with(){}
	        "with(obj){\n_p.push('" +

	        // Convert the template into pure JavaScript
	        str
	          .replace(/[\r\t\n]/g, " ")
	          .split("{%").join("\t")
	          .replace(/((^|%})[^\t]*)'/g, "$1\r")
	          .replace(/\t=(.*?)%}/g, "',$1,'")
	          .split("\t").join("');\n")
	          .split("%}").join("\n_p.push('")
	          .split("\r").join("\\'")
	      + "');}return _p.join('');";

		  frappe.template.debug[name] = fn_str;
		try {
			frappe.template.compiled[key] = new Function("obj", fn_str);
		} catch (e) {
			console.log("Error in Template:");
			console.log(fn_str);
			if(e.lineNumber) {
				console.log("Error in Line "+e.lineNumber+", Col "+e.columnNumber+":");
				console.log(fn_str.split("\n")[e.lineNumber - 1]);
			}
		}
    }

	return frappe.template.compiled[key];
};
frappe.render = function(str, data, name) {
	return frappe.template.compile(str, name)(data);
};
frappe.render_template = function(name, data) {
	if(name.indexOf(' ')!==-1) {
		var template = name;
	} else {
		var template = frappe.templates[name];
	}
	if(data===undefined) {
		data = {};
	}
	return frappe.render(template, data, name);
}
frappe.render_grid = function(opts) {
	// build context
	if(opts.grid) {
		opts.columns = opts.grid.getColumns();
		opts.data = opts.grid.getData().getItems();
	}

	// show landscape view if columns more than 10
	if (opts.landscape == null) {
		if(opts.columns && opts.columns.length > 10) {
			opts.landscape = true;
		} else {
			opts.landscape = false;
		}
	}

	// render content
	if(!opts.content) {
		opts.content = frappe.render_template(opts.template || "print_grid", opts);
	}

	// render HTML wrapper page
	opts.base_url = frappe.urllib.get_base_url();
	opts.print_css = frappe.boot.print_css;
	var html = frappe.render_template("print_template", opts);

	var w = window.open();

	if(!w) {
		frappe.msgprint(__("Please enable pop-ups in your browser"))
	}

	w.document.write(html);
	w.document.close();
},
frappe.render_tree = function(opts) {
	opts.base_url = frappe.urllib.get_base_url();
	opts.landscape = false;
	opts.print_css = frappe.boot.print_css;
	var tree = frappe.render_template("print_tree", opts);
	var w = window.open();

	if(!w) {
		frappe.msgprint(__("Please enable pop-ups in your browser"))
	}

	w.document.write(tree);
	w.document.close();
}
frappe.render_pdf = function(html, opts = {}) {
	//Create a form to place the HTML content
	var formData = new FormData();

	//Push the HTML content into an element
	formData.append("html", html);
	if (opts.orientation) {
		formData.append("orientation", opts.orientation);
	}
	var blob = new Blob([], { type: "text/xml"});
	formData.append("blob", blob);

	var xhr = new XMLHttpRequest();
	xhr.open("POST", '/api/method/frappe.utils.print_format.report_to_pdf');
	xhr.setRequestHeader("X-Frappe-CSRF-Token", frappe.csrf_token);
	xhr.responseType = "arraybuffer";

	xhr.onload = function(success) {
		if (this.status === 200) {
			var blob = new Blob([success.currentTarget.response], {type: "application/pdf"});
			var objectUrl = URL.createObjectURL(blob);

			//Open report in a new window
			window.open(objectUrl);
		}
	};
	xhr.send(formData);
}