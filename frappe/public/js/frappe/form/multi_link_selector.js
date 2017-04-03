// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.MultiLinkSelector = Class.extend({
	init: function(opts) {
		/* help: Options: doctype, get_query, target */
		$.extend(this, opts);

		var me = this;
		if(this.doctype!="[Select]") {
			frappe.model.with_doctype(this.doctype, function(r) {
				me.make();
			});
		} else {
			this.make();
		}
	},
	make: function() {
		me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype=='[Select]') ? __("value") : __(this.doctype)+"s"]),
			fields: [
				{
					fieldtype: "Data", fieldname: this.doctype, label: __("Beginning with"),
					description: __("You can use wildcard %"),
					new_doc: function() {
						var doctype = this.get_options();
						var me = this;

						if(!doctype) return;

						// set values to fill in the new document
						if(this.df.get_route_options_for_new_doc) {
							frappe.route_options = this.df.get_route_options_for_new_doc(this);
						} else {
							frappe.route_options = {};
						}

						// partially entered name field
						frappe.route_options.name_field = this.get_value();

						// reference to calling link
						frappe._from_link = this;
						frappe._from_link_scrollY = $(document).scrollTop();

						frappe.ui.form.quick_entry(doctype, function(doc) {
							if(me.frm) {
								me.parse_validate_and_set_in_model(doc.name);
							} else {
								me.set_value(doc.name);
							}
						});

						return false;
					},
				},
				{
					fieldtype: "HTML", fieldname: "selection_list"
				},
				{
					fieldtype: "Button", fieldname: "clear_list", label: "Clear All"
				},
			],
			primary_action_label: __("Get Items"),
			primary_action: function() {
				me.action();
				// me.get_values();
			}
		});

		if(this.txt)
			this.dialog.fields_dict.txt.set_input(this.txt);

		this.$wrapper = this.dialog.$wrapper;
		this.$input = this.$wrapper.find("input");
		// this.$input = this.dialog.fields_dict.txt.$wrapper;
		this.$selection_list = this.dialog.fields_dict.selection_list.$wrapper;
		this.$clear_list_button = this.$wrapper.find(".btn-xs");

		this.$selection_list.attr("style", "border: 1px solid #d1d8dd; height: 300px; overflow: auto;");
		this.$placeholder = $(`<div class="multilink-empty-state text-extra-muted"> <span class="text-center">
			<i class="fa fa-2x fa-tags"></i> <p>Type to search, select to add</p> </span> </div>`);
		this.$selection_list.append(me.$placeholder);
		this.selected_state = {};
		this.$input.on("focus", function() {
			setTimeout(function() {
				me.$input.trigger("input");
			}, 500);
		});
		this.input = this.$input.get(0);
		this.setup_awesomplete();
		this.setup_result_area();
		this.dialog.show();
	},
	get_values: function() {
		var selections = [];
		var me = this;
		var doctype = this.doctype;
		var object = {};
		Object.keys(this.selected_state).forEach(function(item) {
			if(me.selected_state[item]){
				selections.push(item);
			}
		});
		object[doctype] = selections;

		return object;
	},
	setup_awesomplete: function() {
		var me = this;
		this.$input.cache = {};
		this.awesomplete = new Awesomplete(me.input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],

			// data: function (item, input) {
			// 	var label = item.value + "%%%" + (item.description || "");
			// 	return {
			// 		label: label,
			// 		value: item.value
			// 	};
			// },
			// filter: function(item, input) {
			// 	var value = item.value.toLowerCase();
			// 	if(value.indexOf(input.toLowerCase()) !== -1) {
			// 		return true;
			// 	}
			// },
			// item: function(item, input) {
			// 	var parts = item.split("%%%"),
			// 	d = { value: parts[0], description: parts[1] };
			// 	var _value = d.value;

			// 	if(me.translate_values) {
			// 		_value = __(d.value)
			// 	}
			// 	var html = "<strong>" + _value + "</strong>";
			// 	if(d.description && d.value!==d.description) {
			// 		html += '<br><span class="small">' + __(d.description) + '</span>';
			// 	}
			// 	var hidden = "";
			// 	if(!me.selected_state[d.value]) { hidden = " hide" }
			// 	return $('<li></li>')
			// 		.data('item.autocomplete', d)
			// 		.prop('aria-selected', 'false')
			// 		.html('<a style="display: flex; align-items: center; justify-content: space-around;"><i class="octicon octicon-check' + hidden + '"></i><p>' + html + '</p></a>')
			// 		.get(0);
			// },
			// sort: function(a, b) {
			// 	return 0;
			// }

			data: function (item, input) {
				return {
					label: item.label || item.value,
					value: item.value
				};
			},
			filter: function(item, input) {
				var d = this.get_item(item.value);
				return Awesomplete.FILTER_CONTAINS(d.value, '__link_option') ||
					Awesomplete.FILTER_CONTAINS(d.value, input) ||
					Awesomplete.FILTER_CONTAINS(d.description, input);
			},
			item: function (item, input) {
				d = this.get_item(item.value);
				if(!d.label) {	d.label = d.value; }

				var _label = (me.translate_values) ? __(d.label) : d.label;
				var html = "<strong>" + _label + "</strong>";
				if(d.description && d.value!==d.description) {
					html += '<br><span class="small">' + __(d.description) + '</span>';
				}
				var hidden = "";
				if(!me.selected_state[d.value]) { hidden = " hide" }
				return $('<li style="display: flex; align-items: center; justify-content: flex-start;"></li>')
					.data('item.autocomplete', d)
					.prop('aria-selected', 'false')
					// .html('<a style="display: flex; align-items: center; justify-content: space-around;"><i class="octicon octicon-check' + hidden + '"></i><p>' + html + '</p></a>')
					.html('<span style="flex: 1;"><i class="octicon octicon-check' + hidden + '"></i></span><span style="flex: 15;"><p>' + html + '</p></span>')
					.get(0);
			},
			sort: function(a, b) {
				return 0;
			}
		});

		this.$input.on("input", function(e) {
			var doctype = me.doctype;
			if(!doctype) return;
			if (!me.$input.cache[doctype]) {
				me.$input.cache[doctype] = {};
			}

			var term = e.target.value;

			if (me.$input.cache[doctype][term]!=null) {
				// immediately show from cache
				me.awesomplete.list = me.$input.cache[doctype][term];
			}

			var args = {
				'txt': term,
				'doctype': doctype,
			};

			frappe.call({
				type: "GET",
				method:'frappe.desk.search.search_link',
				no_spinner: true,
				args: args,
				callback: function(r) {
					if(!me.$input.is(":focus")) {
						return;
					}

					// Add new found items to selected states
					r.results.forEach(function(d) {
						if(Object.keys(me.selected_state).indexOf(d.value) === -1) {
							me.selected_state[d.value] = false;
						}
					});

					if(frappe.model.can_create(me.doctype)) {
						// new item
						r.results.push({
							label: "<span class='text-primary link-option'>"
								+ "<i class='fa fa-plus' style='margin-right: 5px;'></i> "
								+ __("Create a new {0}", [__(me.doctype)])
								+ "</span>",
							value: "create_new__link_option",
							action: me.new_doc
						})
					};

					var hidden = "hide";


					me.$input.cache[doctype][term] = [{
							label: 'Select All',
							value: "select_all__link_option",
						}];
					me.$input.cache[doctype][term] = me.$input.cache[doctype][term].concat(r.results);
					me.awesomplete.list = me.$input.cache[doctype][term];
				}
			});
		});

		this.$input.on("awesomplete-open", function(e) {
			me.autocomplete_open = true;
		});

		this.$input.on("awesomplete-close", function(e) {
			me.autocomplete_open = false;
		});

		this.$input.on("awesomplete-select", function(e) {
			e.preventDefault();
			var o = e.originalEvent;
			var $list_item = $(o.origin);
			var item = me.awesomplete.get_item(o.text.value); // item.value, item.description
			var doctype = me.doctype;
			var term = e.target.value;
			if(me.$selection_list.find('.multilink-empty-state').length > 0){
				me.$selection_list.find('.multilink-empty-state').addClass('hide');
			}

			me.autocomplete_open = false;

			// prevent selection on tab
			var TABKEY = 9;
			if(e.keyCode === TABKEY) {
				e.preventDefault();
				me.awesomplete.close();
				return false;
			}
			if(!$list_item.is("li")) {
				$list_item = $list_item.closest("li");
			}

			if(item.value === 'select_all__link_option') {
				console.log("select_all__link_option");
				if($list_item.find("i").hasClass("hide")) {
					$list_item.find("i").removeClass("hide");
					console.log("list item siblings", $list_item.siblings());
					// $list_item.siblings().forEach();

					// update values for only the current list items, or do we need to?

				}
				return;
			}

			$list_item.find("i").toggleClass("hide");
			me.selected_state[o.text.value] = !me.selected_state[o.text.value];

			// me.$input.val(item.value);
			// me.set_value(item.value);

			// add/remove from list to show
			if(me.selected_state[o.text.value]) {
				var row = $(`<div class="list-row" data-name="${item.value}"><div class="row doclist-row">
					<div class="col-xs-12"><div class="row">
					<div class="col-sm-3 list-col ellipsis" title="Item Name: undefined">
					<span class="list-value"> <a class="grey list-id " data-name="${item.value}" href="#Form/Item/Turret1" title="Turret">${item.value}</a></span>
					</div>
					<div class="col-sm-8 list-col ellipsis">
					<span class="text-muted list-value" data-name="Turret1" href="#Form/Item/Turret1" title="Turret">${item.description}</span>
					</div>
					<div class="col-sm-1 list-col ellipsis"><span class="list-value text-muted"> <i class="remove-list-item octicon octicon-x" style="padding-top: 2px"></i></span></div>

					</div></div>
					</div></div>`).appendTo(me.$selection_list);

					row.find("a")
						.attr('data-value', item.value)
						.click(function() {
						var value = $(this).attr("data-value");
						var $link = this;
						return false;
					})
			} else {
				me.$selection_list.find('.list-row[data-name="'+ item.value +'"]').remove();
				if(me.$selection_list.find('.list-row').length < 1) {
					me.$selection_list.find('.multilink-empty-state').removeClass('hide');
				}
			}
			console.log("me.selected state", me.selected_state);

			// update $selection_list area according to me.selected_state, add placeholder if empty


		});

		this.$input.on("awesomplete-selectcomplete", function(e) {
			e.preventDefault();
			var o = e.originalEvent;
			if(o.text.value.indexOf("__link_option") !== -1) {
				me.$input.val("");
			}
		});

	},

	setup_result_area: function() {
		var me = this;
		// Add
		this.$clear_list_button.on('click', function() {
			// update selected items list
			Object.keys(me.selected_state).forEach(function(key) {
				me.selected_state[key] = false;
			});
			me.$selection_list.find('.list-row').remove();
			me.$selection_list.find('.multilink-empty-state').removeClass('hide');
		});
		me.$selection_list.on('click', '.remove-list-item', function() {
			// update selected items list
			var key = $(this).closest('.list-row').attr("data-name");
			me.selected_state[key] = false;
			$(this).closest('.list-row').remove();
			if(me.$selection_list.find('.list-row').length < 1) {
				me.$selection_list.find('.multilink-empty-state').removeClass('hide');
			}
		})
	},

	search: function() {
		var args = {
				txt: this.dialog.fields_dict.txt.get_value(),
				searchfield: "name"
			},
			me = this;

		if(this.target.set_custom_query) {
			this.target.set_custom_query(args);
		}

		// load custom query from grid
		// if(this.target.is_grid && this.target.fieldinfo[this.fieldname]
		// 	&& this.target.fieldinfo[this.fieldname].get_query) {
		// 	$.extend(args,
		// 			this.target.fieldinfo[this.fieldname].get_query(cur_frm.doc));
		// }

		frappe.link_search(this.doctype, args, function(r) {
			var parent = me.dialog.fields_dict.results.$wrapper;
			parent.empty();
			if(r.values.length) {
				$.each(r.values, function(i, v) {
					var row = $(repl('<div class="row link-select-row">\
						<div class="col-xs-4">\
							<b><a href="#">%(name)s</a></b></div>\
						<div class="col-xs-8">\
							<span class="text-muted">%(values)s</span></div>\
						</div>', {
							name: v[0],
							values: v.splice(1).join(", ")
						})).appendTo(parent);



					row.find("a")
						.attr('data-value', v[0])
						.click(function() {
						var value = $(this).attr("data-value");
						var $link = this;
						if(me.target.is_grid) {
							// set in grid
							// me.set_in_grid(value);
						} else {
							if(me.target.doctype)
								me.target.parse_validate_and_set_in_model(value);
							else {
								me.target.set_input(value);
								me.target.$input.trigger("change");
							}
							me.dialog.hide();
						}
						return false;
					})
				})
			} else {
				$('<p><br><span class="text-muted">' + __("No Results") + '</span>'
					+ (frappe.model.can_create(me.doctype) ?
						('<br><br><a class="new-doc btn btn-default btn-sm">'
						+ __("Make a new {0}", [__(me.doctype)]) + "</a>") : '')
					+ '</p>').appendTo(parent).find(".new-doc").click(function() {
						me.target.new_doc();
					});
			}
		}, this.dialog.get_primary_btn());

	},
	// set_in_grid: function(value) {
	// 	var me = this, updated = false;
	// 	if(this.qty_fieldname) {
	// 		frappe.prompt({fieldname:"qty", fieldtype:"Float", label:"Qty",
	// 			"default": 1, reqd: 1}, function(data) {
	// 			$.each(me.target.frm.doc[me.target.df.fieldname] || [], function(i, d) {
	// 				if(d[me.fieldname]===value) {
	// 					frappe.model.set_value(d.doctype, d.name, me.qty_fieldname, data.qty);
	// 					show_alert(__("Added {0} ({1})", [value, d[me.qty_fieldname]]));
	// 					updated = true;
	// 					return false;
	// 				}
	// 			});
	// 			if(!updated) {
	// 				var d = me.target.add_new_row();
	// 				frappe.model.set_value(d.doctype, d.name, me.fieldname, value);
	// 				frappe.after_ajax(function() {
	// 					setTimeout(function() {
	// 						frappe.model.set_value(d.doctype, d.name, me.qty_fieldname, data.qty);
	// 						show_alert(__("Added {0} ({1})", [value, data.qty]));
	// 					}, 100);
	// 				});
	// 			}
	// 		}, __("Set Quantity"), __("Set"));
	// 	} else {
	// 		var d = me.target.add_new_row();
	// 		frappe.model.set_value(d.doctype, d.name, me.fieldname, value);
	// 		show_alert(__("{0} added", [value]));
	// 	}
	// },

});

frappe.link_search = function(doctype, args, callback, btn) {
	if(!args) {
		args = {
			txt: ''
		}
	}
	args.doctype = doctype;
	if(!args.searchfield) {
		args.searchfield = 'name';
	}

	frappe.call({
		method: "frappe.desk.search.search_widget",
		type: "GET",
		args: args,
		callback: function(r) {
			callback && callback(r);
		},
		btn: btn
	});
}

