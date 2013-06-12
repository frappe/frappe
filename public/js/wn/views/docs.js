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
		wn.model.with_doctype("DocType", function() {
			wn.docs.generate_all(logarea);
		})
	})
};

wn.provide("docs");
wn.provide("wn.docs");

wn.docs.generate_all = function(logarea) {
	var pages = [],
		body = $("<div class='docs'>");
		make_page = function(name, links) {
			body.empty();
			var page = new wn.docs.DocsPage({
				namespace: name,
				parent: body,
				links: links
			});
			page.write(function() {
				logarea.append("Writing " + name + "...<br>");
				//logarea.append(".");
				// recurse
				if(page.obj._toc) {
					$.each(page.obj._toc, function(i, child_name) {
						var child_links = {
							parent: name
						};
						if(i < page.obj._toc.length-1) {
							child_links.next_sibling = page.obj._toc[i+1];
						}
						make_page(wn.docs.get_full_name(child_name), child_links);
					});
				}
			});
		}
	
		logarea.empty().append("Downloading server docs...<br>");
		wn.call({
			"method": "webnotes.utils.docs.get_docs",
			callback: function(r) {
				
				// append
				wn.provide("docs.dev").modules = r.message.modules;
				wn.provide("docs.dev.framework.server").webnotes = r.message.webnotes;
				wn.provide("docs.dev.framework.client").wn = wn;
				
				// append static pages to the "docs" object
				$.each(r.message.pages, function(n, content) {
					var parts = content.split("---");
					try {
						var headers = parts.splice(0, 2)[1];
						var obj = JSON.parse(headers);
					} catch(e) {
						msgprint("header parsing error in " + n);
					}
					obj._intro = parts.join("---");
					$.extend(wn.provide(n), obj);
				});
				
				make_page("docs");
			}
		});
	
}

wn.docs.get_full_name = function(name) {
	/* docs:
	Get full name with docs namespace
	*/
	var link_name = name;
	if(name.substr(0,2)==="wn") {
		link_name = "docs.dev.framework.client." + name;
	}
	if(name.substr(0,8)==="webnotes") {
		link_name = "docs.dev.framework.server." + name;
	}
	return link_name;	
}

wn.docs.get_short_name = function(namespace) {
	namespace = namespace.replace("docs.dev.framework.server.", "")
	namespace = namespace.replace("docs.dev.framework.client.", "")
	return namespace;
}

wn.docs.get_title = function(namespace) {
	var obj = wn.provide(namespace);
	return obj._label || wn.docs.get_short_name(namespace)
}

wn.docs.DocsPage = Class.extend({
	init: function(opts) {
		/* docs: create js documentation */
		$.extend(this, opts);
		
		var obj = wn.provide(this.namespace),
			me = this;

		obj = (obj._type == "class" && obj.prototype) ? obj.prototype : obj;
		if(obj._toc && this.links)
			this.links.first_child = obj._toc[0];
		
		this.obj = obj;
		this.make(obj);
	},
	make: function(obj) {
		this.make_title(obj);
		this.make_breadcrumbs(obj);
		this.make_intro(obj);
		this.make_toc(obj);
		if(obj._type==="model") {
			this.make_docproperties(obj);
			this.make_docfields(obj);
		}
		if(obj._type=="permissions")
			this.make_docperms(obj);
		if(obj._type==="controller_client")
			this.make_obj_from_cur_frm(obj);
		this.make_functions(obj);
		if(this.links) {
			this.make_links();
		}
	},
	make_links: function() {
		if(this.links.parent) {
			var btn_group = $('<div class="btn-group pull-right" \
				style="margin: 15px 0px;">')
				.appendTo(this.parent)
			$("<a class='btn btn-default'>")
				.html('<i class="icon-arrow-up"></i> ' 
					+ wn.docs.get_title(this.links.parent))
				.attr("href", this.links.parent + ".html")
				.appendTo(btn_group)
			if(this.links.next_sibling) {
				$("<a class='btn btn-info'>")
					.html('<i class="icon-arrow-right"></i> ' 
						+ wn.docs.get_title(this.links.next_sibling))
					.attr("href", wn.docs.get_full_name(this.links.next_sibling) + ".html")
					.appendTo(btn_group)
			} 
			if (this.links.first_child) {
				$("<a class='btn btn-info'>")
					.html('<i class="icon-arrow-down"></i> ' 
						+ wn.docs.get_title(this.links.first_child))
					.attr("href", wn.docs.get_full_name(this.links.first_child) + ".html")
					.appendTo(btn_group)
			}
		}
	},
	make_title: function(obj) {
		if(!obj._no_title) {
			if(obj._title_image && false) {
				var outer = $("<div>")
					.css({
						"background-image": "url(docs/" + obj._title_image + ")",
						"background-size": "100%",
						"background-position": "center-top",
						"margin-bottom": "30px",
						"border-radius": "5px"
					})
					.appendTo(this.parent)
		 			var inner = $("<div>")
						.appendTo(outer)
						.css({
							"text-align": "center",
							"background-color": "rgba(0,0,0,0.4)",
							"color": "white",
							"padding": "240px 20px 220px 20px"
						})
					var head = $("<h1>").appendTo(inner);
			} else {
				var head = $("<h1>").appendTo(this.parent);
			}
			
			head.html(obj._label || wn.docs.get_short_name(this.namespace))
		}
	},
	make_breadcrumbs: function(obj) {
		var me = this,
			name = this.namespace

		if(name==="docs") return;
			
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
			label: obj._label || wn.docs.get_short_name(this.namespace)
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
				var link_name = wn.docs.get_full_name(name);
				$(repl('<li><a href="%(link_name)s.html">%(label)s</a></li>', {
						link_name: link_name,
						label: wn.provide(link_name)._label || name
					}))
					.appendTo(ol)
			})
		}
	},
	
	make_docproperties: function(obj) {
		var me = this;

		this.h3("Properties");
		var tbody = this.get_tbody([
				{label:"Property", width: "25%"},
				{label:"Value", width: "25%"},
				{label:"Description", width: "50%"},
			]);
			
		$.each(wn.model.get("DocField", {parent:"DocType"}), function(i, df) {
			if(wn.model.no_value_type.indexOf(df.fieldtype)===-1) {
				if(!df.description) df.description = "";
				df.value = obj._properties[df.fieldname] || "";
				$(repl('<tr>\
					<td>%(label)s</td>\
					<td>%(value)s</td>\
					<td>%(description)s</td>\
				</tr>', df)).appendTo(tbody);
			}
		});
	},
	
	make_docfields: function(obj) {
		var me = this,
			docfields = obj._fields;

		if(docfields.length) {
			this.h3("DocFields");
			var tbody = this.get_tbody([
					{label:"Sr", width: "10%"},
					{label:"Fieldname", width: "25%"},
					{label:"Label", width: "20%"},
					{label:"Field Type", width: "25%"},
					{label:"Options", width: "20%"},
				]);
			docfields = docfields.sort(function(a, b) { return a.idx > b.idx ? 1 : -1 })
			$.each(docfields, function(i, df) {
				$(repl('<tr>\
					<td>%(idx)s</td>\
					<td>%(fieldname)s</td>\
					<td>%(label)s</td>\
					<td>%(fieldtype)s</td>\
					<td>%(options)s</td>\
				</tr>', df)).appendTo(tbody);
			});
		};
	},
	make_docperms: function(obj) {
		var me = this;
		if(obj._permissions.length) {
			this.h3("Permissions");
			var tbody = this.get_tbody([
					{label:"Sr", width: "8%"},
					{label:"Role", width: "20%"},
					{label:"Level", width: "7%"},
					{label:"Read", width: "7%"},
					{label:"Write", width: "8%"},
					{label:"Create", width: "8%"},
					{label:"Submit", width: "8%"},
					{label:"Cancel", width: "8%"},
					{label:"Amend", width: "8%"},
					{label:"Report", width: "8%"},
					{label:"Match", width: "10%"},
				]);
			obj._permissions = obj._permissions.sort(function(a, b) { 
				return a.idx > b.idx ? 1 : -1 
			})
			$.each(obj._permissions, function(i, perm) {
				if(!perm.match) perm.match = "";
				$.each(perm, function(key, val) {
					if(val==null) perm[key] = "";
				});
				$(repl('<tr>\
					<td>%(idx)s</td>\
					<td>%(role)s</td>\
					<td>%(permlevel)s</td>\
					<td>%(read)s</td>\
					<td>%(write)s</td>\
					<td>%(create)s</td>\
					<td>%(submit)s</td>\
					<td>%(cancel)s</td>\
					<td>%(amend)s</td>\
					<td>%(report)s</td>\
					<td>%(match)s</td>\
				</tr>', perm)).appendTo(tbody);
			});
		};
	},
	make_obj_from_cur_frm: function(obj) {
		var me = this;
		obj._fetches = [];
		cur_frm = {
			set_query: function() {
				
			},
			cscript: {},
			pformat: {},
			add_fetch: function() {
				obj._fetches.push(arguments)
			},
			fields_dict: {}
		};
		$.each(obj._fields, function(i, f) { 
			cur_frm.fields_dict[f] = {
				grid: {
					get_field: function(fieldname) {
						return {}
					}
				}
			}}
		);
		var tmp = eval(obj._code);
		$.extend(obj, cur_frm.cscript);
	},
	make_functions: function(obj) {
		var functions = this.get_functions(obj);
		if(!$.isEmptyObject(functions)) {
			this.h3(obj._type === "class" ? "Methods" : "Functions");
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
			tbody = this.get_tbody();
			
		$.each(functions, function(name, value) {
			me.render_function(name, value, tbody, namespace)
		});
	},
	get_tbody: function(columns) {
		table = $("<table class='table table-bordered' style='table-layout: fixed;'>\
			<thead></thead>\
			<tbody></tbody>\
		</table>").appendTo(this.parent);
		if(columns) {
			$.each(columns, function(i, c) {
				$("<th>")
					.css({"width": c.width})
					.html(c.label)
					.appendTo(table.find("thead"))
			});
		}
		return table.find("tbody");
	},
	h3: function(txt) {
		$("<h3>").html(txt).appendTo(this.parent);
	},
	render_function: function(name, value, parent, namespace) {
		var me = this,
			code = value.toString();
		
		namespace = namespace===undefined ? 
			((this.obj._type==="class" || this.obj._type==="controller_client") ? 
				"" : this.namespace) 
			: "";

		if(this.obj._function_namespace)
			namespace = this.obj._function_namespace;

		if(namespace!=="") {
			namespace = wn.docs.get_short_name(namespace);
		}

		if(namespace!=="" && namespace[namespace.length-1]!==".")
			namespace = namespace + ".";

		var args = this.get_args(value);
		
		var help = value._help || code.split("/* docs:")[1];
		if(help && help.indexOf("*/")!==-1) help = help.split("*/")[0];

		var source = "";
		if(code.substr(0, 8)==="function" || value._source) {
			source = repl('<p style="font-size: 90%;">\
				<a href="#" data-toggle="%(name)s">View Source</a></p>\
				<pre data-target="%(name)s" style="display: none; font-size: 11px; \
						background-color: white; border-radius: 0px;\
						overflow-x: auto; word-wrap: normal;"><code class="language-%(lang)s">\
%(code)s</code></pre>', {
				name: name,
				code: value._source || code,
				lang: (value._source ? "python" : "javascript")
			});
		}
		
		try {
			$(repl('<tr>\
				<td style="width: 30%;">%(name)s</td>\
				<td>\
					<h5>Usage:</h5>\
					<pre>%(namespace)s%(name)s(%(args)s)</pre>\
					%(help)s\
					%(source)s\
				</td>\
			</tr>', {
				name: name,
				namespace: namespace,
				args: args,
				help: help ? wn.markdown(help) : "",
				source: source
			})).appendTo(parent)
		} catch(e) {
			console.log(e);
			console.log(code);
		}
	},
	get_args: function(obj) {
		if(obj._args) 
			return obj._args.join(", ");
		else
			return obj.toString().split("function")[1].split("(")[1].split(")")[0];
	},
	write: function(callback) {
		wn.call({
			method: "webnotes.utils.docs.write_doc_file",
			args: {
				name: this.namespace,
				title: this.obj._label || wn.docs.get_short_name(this.namespace),
				html: html_beautify(this.parent.html())
			},
			callback: function(r) {
				callback();
			}
		});
	}
})