/*

Todo:
- make global toc
- static pages in markdown (in sources folder)
	- web interface
	- building an application
	- customizing an application
	- generating web pages
	
- help / comments in markdown
- pages
- doctype
	- links
	- properties
	- methods
	- events (server, client)

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
	
	var body = $(wrapper).find(".layout-main"),
		logarea = $('<div class="well"></div>').appendTo(body);
	
	wrapper.appframe.add_button("Make Docs", function() {
		wn.docs.generate_all(logarea);
	})
};

wn.provide("docs");
wn.provide("wn.docs")

$.extend(docs, {
	_label: "Documentation",
	_description: "Complete Application Documentation",
	_toc: [
		"docs.quickstart",
		"docs.framework",
		"docs.modules"
	],
	"framework": {
		_label: "Framework API",
		_intro: "Detailed documentation of all functions and Classes for both client\
			and server side development.",
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
	"modules": {
		_type: "Application",
		_label: "Application Modules"
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
			page.write(function() {
				//logarea.append("Writing " + name + "...<br>");
				logarea.append(".");
				// recurse
				if(page.obj._toc) {
					$.each(page.obj._toc, function(i, name) {
						make_page(name);
					})
				}
			});
		}
	
		logarea.empty().append("Downloading server docs...<br>");
		wn.call({
			"method": "webnotes.utils.docs.get_docs",
			callback: function(r) {
				window.webnotes = r.message.webnotes;
				docs.modules = r.message.modules;
				
				// append static pages to the "docs" object
				$.each(r.message.pages, function(n, content) {
					var parts = content.split("---");
					var obj = JSON.parse(parts.splice(0, 2)[1]);
					obj._intro = parts.join("---");
					$.extend(wn.provide(n), obj);
				});
				
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
		if(obj._type==="doctype")
			this.make_docfields(obj);
		this.make_functions(obj);
	},
	make_breadcrumbs: function(obj) {
		var me = this,
			name = this.namespace

		if(name==="docs") return;
			
		if(name==="wn" || name.substr(0,3)==="wn.") {
			name = "docs.framework.client." + name;
		}
		if(name==="webnotes" || name.substr(0,9)==="webnotes.") {
			name = "docs.framework.server." + name;
		}

		var parts = name.split("."),
			ul = $('<ul class="breadcrumb">').appendTo(this.parent),
			fullname = "";
					
		$.each(parts, function(i, p) {
			if(i!=parts.length-1) {
				if(fullname) 
					fullname = fullname + "." + p
				else 
					fullname = p
				$(repl('<li><a href="%(name)s.html">%(label)s</a></li>', {
					name: fullname,
					label: wn.provide(fullname)._label || p
				})).appendTo(ul);
			}
		});

		$(repl('<li class="active">%(label)s</li>', {
			label: obj._label || this.namespace
		})).appendTo(ul)
	},
	make_intro: function(obj) {
		if(obj._intro) {
			$("<p>").html(wn.markdown(obj._intro)).appendTo(this.parent);
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
	make_docfields: function(obj) {
		var me = this,
			docfields = [];
		$.each(obj, function(name, value) {
			if(value && value._type=="docfield") {
				docfields.push(value);
			};
		})
		if(docfields.length) {
			this.h3("DocFields");
			var tbody = this.get_tbody();
			docfields = docfields.sort(function(a, b) { return a.idx > b.idx ? 1 : -1 })
			$.each(docfields, function(i, df) {
				$(repl('<tr>\
					<td style="width: 10%;">%(idx)s</td>\
					<td style="width: 25%;">%(fieldname)s</td>\
					<td style="width: 20%;">%(label)s</td>\
					<td style="width: 25%;">%(fieldtype)s</td>\
					<td style="width: 20%;">%(options)s</td>\
				</tr>', df)).appendTo(tbody);
			});
		};
	},
	make_functions: function(obj) {
		var functions = this.get_functions(obj);
		if(!$.isEmptyObject(functions)) {
			this.h3("Functions");
			this.make_function_table(functions);
		}
	},
	get_functions: function(obj) {
		var functions = {},
			tbody = this.get_tbody();
		
		$.each(obj || {}, function(name, value) {
			if(value && ((typeof value==="function" && typeof value.init !== "function")
				|| value._type === "function")) 
					functions[name] = value;
		});
		return functions;
	},
	make_function_table: function(functions, namespace) {
		var me = this,
			tbody = this.get_tbody();
			
		$.each(functions, function(name, value) {
			me.render_function(name, value, tbody, namespace)
		});
	},
	get_tbody: function() {
		table = $("<table class='table table-bordered'><tbody></tbody>\
		</table>").appendTo(this.parent),
		tbody = table.find("tbody");
		return tbody;
	},
	h3: function(txt) {
		$("<h3>").html(txt).appendTo(this.parent);
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
	write: function(callback) {
		wn.call({
			method: "webnotes.utils.docs.write_doc_file",
			args: {
				name: this.namespace,
				html: html_beautify(this.parent.html())
			},
			callback: function(r) {
				callback();
			}
		});
	}
})