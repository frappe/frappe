/*

Documentation API

Every module (namespace) / class will have a page
- _toc
- _path
- _label
- _intro
- _type (class, function, module, doctype etc)
- [list of functions / objects / classes]
*/

wn.standard_pages["docs"] = function() {
	var wrapper = wn.container.add_page('docs');

	wn.ui.make_app_page({
		parent: wrapper,
		single_column: true,
		title: wn._("Docs")
	});
	
	var body = $(wrapper).find(".layout-main");
	
	$(wrapper).on("show", function() {
		body.empty();
		new wn.docs.DocsPage({
			namespace: wn.get_route()[1] || "docs",
			parent: body,
			wrapper: wrapper
		});
	});
};

wn.provide("docs");
wn.provide("wn.docs")

$.extend(docs, {
	_label: "Documentation",
	_description: "Complete Application Documentation",
	_toc: [
		"docs.framework",
		"docs.core",
		"docs.modules"
	],
	"framework": {
		_label: "Framework API",
		_intro: "Detailed documentation of all functions and Classes for both client\
			and server side development.",
		_path: ["docs"],
		_toc: [
			"docs.framework.server",
			"docs.framework.client"
		],
		"server": {
			_label: "Server Side - Python",
			_toc: [
				"webnotes",
				"webnotes.auth",
				"webnotes.boot",
				"webnotes.db",
				"webnotes.client",
				"webnotes.model",
				"webnotes.utils",
				"webnotes.widgets"
			]
		},
		"client": {
			_label: "Client Side - JavaScript",
			_toc: [
				"wn", 
				"wn.model", 
				"wn.ui", 
				"wn.views", 
				"wn.utils"
			]
		}
	},
	"core": {
		_type: "Module",
	},
	"modules": {
		_type: "Application"
	}
});

wn.docs.DocsPage = Class.extend({
	init: function(opts) {
		/* docs: create js documentation */
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var obj = wn.provide(this.namespace);
		$("<h2>").html(obj._label || this.namespace).appendTo(this.parent);
		this.make_breadcrumbs(obj);
		this.make_intro(obj);
		this.make_toc(obj);
		this.make_classes(obj);
		this.make_functions(obj);
	},
	make_breadcrumbs: function(obj) {
		var me = this;
		if(obj._path) {
			var ul = $('<ul class="breadcrumb">').appendTo(this.parent);
			$.each(obj._path, function(i, p) {
				$(repl('<li><a href="#docs/%(name)s">%(label)s</a></li>', {
					name: p,
					label: wn.provide(p)._label || p
				})).appendTo(ul)
			});
			$(repl('<li class="active">%(label)s</li>', {
				label: obj._label || this.namespace
			})).appendTo(ul)
		}
	},
	make_intro: function(obj) {
		if(obj._intro) {
			$("<p>").html(obj._intro).appendTo(this.parent);
		}
	},
	make_toc: function(obj) {
		if(obj._toc) {
			var body = $("<div class='well'>")
				.appendTo(this.parent);
			$("<h4>Contents</h4>").appendTo(body);
			var ol = $("<ol>").appendTo(body);
			$.each(obj._toc, function(i, name) {
				$(repl('<li><a href="#docs/%(name)s">%(label)s</a></li>', {
						name: name,
						label: wn.provide(name)._label || name
					}))
					.appendTo(ol)
			})
		}
	},
	make_classes: function(obj) {
		var me = this,
			classes = {}
		$.each(obj, function(name, value) {
			if(value._type=="class") {
				classes[name] = value;
			};
		})
		if(!$.isEmptyObject(classes)) {
			$("<h3>").html("Classes").appendTo(this.parent);
			$.each(classes, function(name, value) {
				$("<h4>").html("Class: " + name).appendTo(me.parent);
				me.make_function_table(me.get_functions(value.prototype), "");
				$("<hr>").appendTo(me.parent);
			})
		}
	},
	make_functions: function(obj) {
		var functions = this.get_functions(obj);
		if(!$.isEmptyObject(functions)) {
			$("<h3>").html("Functions").appendTo(this.parent);
			this.make_function_table(functions);
		}
	},
	get_functions: function(obj) {
		var functions = {};
		$.each(obj, function(name, value) {
			if(typeof value=="function" 
				&& (value._type || "function")=="function") 
					functions[name] = value;
		});
		return functions;
	},
	make_function_table: function(functions, namespace) {
		var me = this,
			table = $("<table class='table table-bordered'><tbody></tbody>\
			</table>").appendTo(this.parent),
			tbody = table.find("tbody");

		$.each(functions, function(name, value) {
			me.render_function(name, value, tbody, namespace)
		});
	},
	render_function: function(name, value, parent, namespace) {
		var me = this,
			code = value.toString();
			
		namespace = namespace===undefined ? this.namespace : "";

		if(namespace!=="" && namespace[namespace.length-1]!==".")
			namespace = namespace + ".";
			
		if(code.indexOf("/* options")===-1) {
			var args = code.split("function")[1].split("(")[1].split(")")[0];
		} else {
			var args = "options",
				options = JSON.parse(code.split("/* options:")[1].split("*/")[0]);

			options = "<h5>Options: </h5><table class='table table-bordered'><tbody>" 
				+ $.map(options, function(o, i) {
					var i = o.indexOf(":");
					return repl('<tr>\
						<td style="width: 30%">%(key)s</td>\
						<td>%(value)s</td></tr>', {
							key: o.slice(0, i),
							value: o.slice(i+1)
						})
				}).join("") + "</tbody></table>";
			
		}
		var help = code.split("/* help:")[1]
			if(help) help = help.split("*/")[0];
		$(repl('<tr>\
			<td style="width: 30%;">%(name)s</td>\
			<td>\
				%(help)s\
				<h5>Usage:</h5>\
				<pre>%(namespace)s%(name)s(%(args)s)</pre>\
				%(options)s\
			</td>\
		</tr>', {
			name: name,
			namespace: namespace,
			args: args,
			options: options || "",
			help: help ? ("<p>" + help + "</p>") : ""
		})).appendTo(parent)
		
	}
})