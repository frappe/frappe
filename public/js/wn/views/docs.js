/*

Todo:
- modules / doctypes (export)
- auto breadcrumbs
- make global toc
- help / comments in markdown
- jinja template for docs

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
	wn.require("lib/js/lib/beautify-html.js");

	wn.ui.make_app_page({
		parent: wrapper,
		single_column: true,
		title: wn._("Docs")
	});
	
	var body = $(wrapper).find(".layout-main");
	wn.docs.generate_all($('<div class="well"></div>').appendTo(body));
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

wn.docs.generate_all = function(logarea) {
	var pages = [],
		body = $("<div class='docs'>");
		make_page = function(name) {
			body.empty();
			var page = new wn.docs.DocsPage({
				namespace: name,
				parent: body,
			});
			logarea.append(".");
			page.write();
			
			// recurse
			if(page.obj._toc) {
				$.each(page.obj._toc, function(i, name) {
					make_page(name);
				})
			}
		}
	
		wn.call({
			"method": "webnotes.utils.docs.get_docs",
			callback: function(r) {
				window.webnotes = r.message.webnotes;
				make_page("docs");
			}
		});
	
}

wn.docs.DocsPage = Class.extend({
	init: function(opts) {
		/* docs: create js documentation */
		$.extend(this, opts);
		
		var obj = wn.provide(this.namespace),
			me = this;

		obj = (obj._type == "class" && obj.prototype) ? obj.prototype : obj;
		
		this.obj = obj;
		this.make(obj);
	},
	make: function(obj) {
		$("<h2>").html(obj._label || this.namespace).appendTo(this.parent);
		this.make_breadcrumbs(obj);
		this.make_intro(obj);
		this.make_toc(obj);
		//this.make_classes(obj);
		this.make_functions(obj);
	},
	make_breadcrumbs: function(obj) {
		var me = this;
		if(obj._path) {
			var ul = $('<ul class="breadcrumb">').appendTo(this.parent);
			$.each(obj._path, function(i, p) {
				$(repl('<li><a href="%(name)s.html">%(label)s</a></li>', {
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
				$(repl('<li><a href="%(name)s.html">%(label)s</a></li>', {
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
			if(value && value._type=="class") {
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

		$.each(obj || {}, function(name, value) {
			if(value && ((typeof value==="function" && typeof value.init !== "function")
				|| value._type === "function")) 
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
			var args = this.get_args(value);
				options = this.make_parameters("Parameters", 
					JSON.parse(this.get_property(value, "parameters") || "{}"));
		} else {
			var args = "options",
				options = this.make_parameters("Options", 
					JSON.parse(this.get_property(value, "options") || "{}"));
		}
		
		var example = this.get_property(value, "example");
		example = example ? ("<h5>Example</h5><pre>" + example.replace(/\t/g, "") + "</pre>") : "";
		
		var help = code.split("/* help:")[1]
			if(help) help = help.split("*/")[0];
		$(repl('<tr>\
			<td style="width: 30%;">%(name)s</td>\
			<td>\
				%(help)s\
				<h5>Usage:</h5>\
				<pre>%(namespace)s%(name)s(%(args)s)</pre>\
				%(options)s%(example)s\
			</td>\
		</tr>', {
			name: name,
			namespace: namespace,
			args: args,
			example: example || "",
			options: options || "",
			help: help ? ("<p>" + help + "</p>") : ""
		})).appendTo(parent)
	},
	get_args: function(obj) {
		if(obj._args) 
			return obj._args.join(", ");
		else
			return obj.toString().split("function")[1].split("(")[1].split(")")[0];
	},
	get_property: function(obj, property) {
		if(obj["_" + property])
			return obj["_" + property];
		var code = obj.toString();
		if(code.indexOf("/* " + property + ":")!==-1) {
			return code.split("/* " + property + ":")[1].split("*/")[0]
		}
		return "";
	},
	make_parameters: function(title, options) {
		if($.isEmptyObject(options)) 
			return "";
		return  "<h5>"+title+"</h5><table class='table table-bordered'><tbody>" 
			+ $.map(options, function(o, i) {
				var i = o.indexOf(":");
				return repl('<tr>\
					<td style="width: 30%">%(key)s</td>\
					<td>%(value)s</td></tr>', {
						key: o.slice(0, i),
						value: o.slice(i+1)
					})
			}).join("") + "</tbody></table>";
	},
	write: function() {
		wn.call({
			method: "webnotes.utils.docs.write_doc_file",
			args: {
				name: this.namespace,
				html: html_beautify(this.parent.html())
			},
			callback: function(r) {
				
			}
		});
	}
})