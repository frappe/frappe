// special features for link
// buttons
// autocomplete
// link validation
// custom queries
// add_fetches
import Awesomplete from "awesomplete";

frappe.ui.form.recent_link_validations = {};

frappe.ui.form.ControlLink = class ControlLink extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false;
	make_input() {
		var me = this;
		$(`<div class="link-field ui-front" style="position: relative;">
			<input type="text" class="input-with-feedback form-control">
			<span class="link-btn">
				<a class="btn-open no-decoration" title="${__("Open Link")}">
					${frappe.utils.icon("arrow-right", "xs")}
				</a>
			</span>
		</div>`).prependTo(this.input_area);
		this.$input_area = $(this.input_area);
		this.$input = this.$input_area.find("input");
		this.$link = this.$input_area.find(".link-btn");
		this.$link_open = this.$link.find(".btn-open");
		this.set_input_attributes();
		this.$input.on("focus", function () {
			setTimeout(function () {
				if (me.$input.val() && me.get_options()) {
					let doctype = me.get_options();
					let name = me.get_input_value();
					me.$link.toggle(true);
					me.$link_open.attr("href", frappe.utils.get_form_link(doctype, name));
				}

				if (!me.$input.val()) {
					me.$input.val("").trigger("input");

					// hide link arrow to doctype if none is set
					me.$link.toggle(false);
				}
			}, 500);
		});
		this.$input.on("blur", function () {
			// if this disappears immediately, the user's click
			// does not register, hence timeout
			setTimeout(function () {
				me.$link.toggle(false);
			}, 500);
		});
		this.$input.attr("data-target", this.df.options);
		this.input = this.$input.get(0);
		this.has_input = true;
		this.translate_values = true;
		this.setup_buttons();
		this.setup_awesomeplete();
		this.bind_change_event();
	}
	get_options() {
		return this.df.options;
	}
	get_reference_doctype() {
		// this is used to get the context in which link field is loaded
		if (this.doctype) return this.doctype;
		else {
			return frappe.get_route && frappe.get_route()[0] === "List"
				? frappe.get_route()[1]
				: null;
		}
	}
	setup_buttons() {
		if (this.only_input && !this.with_link_btn) {
			this.$input_area.find(".link-btn").remove();
		}
	}
	set_formatted_input(value) {
		super.set_formatted_input();
		if (!value) return;

		if (!this.title_value_map) {
			this.title_value_map = {};
		}
		this.set_link_title(value);
	}
	get_translated(value) {
		return this.is_translatable() ? __(value) : value;
	}
	is_translatable() {
		return in_list(frappe.boot?.translated_doctypes || [], this.get_options());
	}
	is_title_link() {
		return in_list(frappe.boot?.link_title_doctypes || [], this.get_options());
	}
	async set_link_title(value) {
		const doctype = this.get_options();

		if (!doctype || !this.is_title_link()) {
			this.translate_and_set_input_value(value, value);
			return;
		}

		const link_title =
			frappe.utils.get_link_title(doctype, value) ||
			(await frappe.utils.fetch_link_title(doctype, value));

		this.translate_and_set_input_value(link_title, value);
	}
	translate_and_set_input_value(link_title, value) {
		let translated_link_text = this.get_translated(link_title);
		this.title_value_map[translated_link_text] = value;

		this.set_input_value(translated_link_text);
	}
	parse_validate_and_set_in_model(value, e, label) {
		if (this.parse) value = this.parse(value, label);
		if (label) {
			this.label = this.get_translated(label);
			frappe.utils.add_link_title(this.df.options, value, label);
		}

		return this.validate_and_set_in_model(value, e, true);
	}
	parse(value) {
		return strip_html(value);
	}
	get_input_value() {
		if (this.$input) {
			const input_value = this.$input.val();
			return this.title_value_map?.[input_value] || input_value;
		}
		return null;
	}
	get_label_value() {
		return this.$input ? this.$input.val() : "";
	}
	set_input_value(value) {
		this.$input && this.$input.val(value);
	}
	open_advanced_search() {
		var doctype = this.get_options();
		if (!doctype) return;
		new frappe.ui.form.LinkSelector({
			doctype: doctype,
			target: this,
			txt: this.get_input_value(),
		});
		return false;
	}
	new_doc() {
		var doctype = this.get_options();
		var me = this;

		if (!doctype) return;

		let df = this.df;
		if (this.frm && this.frm.doctype !== this.df.parent) {
			// incase of grid use common df set in grid
			df = this.frm.get_docfield(this.doc.parentfield, this.df.fieldname);
		}
		// set values to fill in the new document
		if (df && df.get_route_options_for_new_doc) {
			frappe.route_options = df.get_route_options_for_new_doc(this);
		} else {
			frappe.route_options = {};
		}

		// partially entered name field
		frappe.route_options.name_field = this.get_label_value();

		// reference to calling link
		frappe._from_link = frappe.utils.deep_clone(this);
		frappe._from_link_scrollY = $(document).scrollTop();

		frappe.ui.form.make_quick_entry(doctype, (doc) => {
			return me.set_value(doc.name);
		});

		return false;
	}
	setup_awesomeplete() {
		let me = this;

		this.$input.cache = {};

		this.awesomplete = new Awesomplete(me.input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			replace: function (item) {
				// Override Awesomeplete replace function as it is used to set the input value
				// https://github.com/LeaVerou/awesomplete/issues/17104#issuecomment-359185403
				this.input.value = me.get_translated(item.label || item.value);
			},
			data: function (item) {
				return {
					label: me.get_translated(item.label || item.value),
					value: item.value,
				};
			},
			filter: function () {
				return true;
			},
			item: function (item) {
				let d = this.get_item(item.value);
				if (!d.label) {
					d.label = d.value;
				}

				let _label = me.get_translated(d.label);
				let html = d.html || "<strong>" + _label + "</strong>";
				if (
					d.description &&
					// for title links, we want to inlude the value in the description
					// because it will not visible otherwise
					(me.is_title_link() || d.value !== d.description)
				) {
					html += '<br><span class="small">' + __(d.description) + "</span>";
				}
				return $("<li></li>")
					.data("item.autocomplete", d)
					.prop("aria-selected", "false")
					.html(`<a><p title="${_label}">${html}</p></a>`)
					.get(0);
			},
			sort: function () {
				return 0;
			},
		});

		this.custom_awesomplete_filter && this.custom_awesomplete_filter(this.awesomplete);

		this.$input.on(
			"input",
			frappe.utils.debounce(function (e) {
				var doctype = me.get_options();
				if (!doctype) return;
				if (!me.$input.cache[doctype]) {
					me.$input.cache[doctype] = {};
				}

				var term = e.target.value;

				if (me.$input.cache[doctype][term] != null) {
					// immediately show from cache
					me.awesomplete.list = me.$input.cache[doctype][term];
				}
				var args = {
					txt: term,
					doctype: doctype,
					ignore_user_permissions: me.df.ignore_user_permissions,
					reference_doctype: me.get_reference_doctype() || "",
				};

				me.set_custom_query(args);

				frappe.call({
					type: "POST",
					method: "frappe.desk.search.search_link",
					no_spinner: true,
					args: args,
					callback: function (r) {
						if (!window.Cypress && !me.$input.is(":focus")) {
							return;
						}
						r.results = me.merge_duplicates(r.results);

						// show filter description in awesomplete
						if (args.filters) {
							let filter_string = me.get_filter_description(args.filters);
							if (filter_string) {
								r.results.push({
									html: `<span class="text-muted" style="line-height: 1.5">${filter_string}</span>`,
									value: "",
									action: () => {},
								});
							}
						}

						if (!me.df.only_select) {
							if (frappe.model.can_create(doctype)) {
								// new item
								r.results.push({
									html:
										"<span class='text-primary link-option'>" +
										"<i class='fa fa-plus' style='margin-right: 5px;'></i> " +
										__("Create a new {0}", [__(me.get_options())]) +
										"</span>",
									label: __("Create a new {0}", [__(me.get_options())]),
									value: "create_new__link_option",
									action: me.new_doc,
								});
							}

							//custom link actions
							let custom__link_options =
								frappe.ui.form.ControlLink.link_options &&
								frappe.ui.form.ControlLink.link_options(me);

							if (custom__link_options) {
								r.results = r.results.concat(custom__link_options);
							}

							// advanced search
							if (locals && locals["DocType"]) {
								// not applicable in web forms
								r.results.push({
									html:
										"<span class='text-primary link-option'>" +
										"<i class='fa fa-search' style='margin-right: 5px;'></i> " +
										__("Advanced Search") +
										"</span>",
									label: __("Advanced Search"),
									value: "advanced_search__link_option",
									action: me.open_advanced_search,
								});
							}
						}
						me.$input.cache[doctype][term] = r.results;
						me.awesomplete.list = me.$input.cache[doctype][term];
						me.toggle_href(doctype);
					},
				});
			}, 500)
		);

		this.$input.on("blur", function () {
			if (me.selected) {
				me.selected = false;
				return;
			}
			let value = me.get_input_value();
			let label = me.get_label_value();
			let last_value = me.last_value || "";
			let last_label = me.label || "";

			if (value !== last_value) {
				me.parse_validate_and_set_in_model(value, null, label);
			}
		});

		this.$input.on("awesomplete-open", () => {
			this.autocomplete_open = true;

			if (!me.get_label_value()) {
				// hide link arrow to doctype if none is set
				me.$link.toggle(false);
			}
		});

		this.$input.on("awesomplete-close", (e) => {
			this.autocomplete_open = false;

			if (!me.get_label_value()) {
				// hide link arrow to doctype if none is set
				me.$link.toggle(false);
			}
		});

		this.$input.on("awesomplete-select", function (e) {
			var o = e.originalEvent;
			var item = me.awesomplete.get_item(o.text.value);

			me.autocomplete_open = false;

			// prevent selection on tab
			let TABKEY = 9;
			if (e.keyCode === TABKEY) {
				e.preventDefault();
				me.awesomplete.close();
				return false;
			}

			if (item.action) {
				item.value = "";
				item.label = "";
				item.action.apply(me);
			}

			// if remember_last_selected is checked in the doctype against the field,
			// then add this value
			// to defaults so you do not need to set it again
			// unless it is changed.
			if (me.df.remember_last_selected_value) {
				frappe.boot.user.last_selected_values[me.df.options] = item.value;
			}

			me.parse_validate_and_set_in_model(item.value, null, item.label);
		});

		this.$input.on("awesomplete-selectcomplete", function (e) {
			let o = e.originalEvent;
			if (o.text.value.indexOf("__link_option") !== -1) {
				me.$input.val("");
			}
		});
	}

	show_untranslated() {
		let value = this.get_input_value();
		this.is_translatable() && this.set_input_value(value);
	}

	merge_duplicates(results) {
		// in case of result like this
		// [{value: 'Manufacturer 1', 'description': 'mobile part 1'},
		// 	{value: 'Manufacturer 1', 'description': 'mobile part 2'}]
		// suggestion list has two items with same value (docname) & description
		return results.reduce((newArr, currElem) => {
			if (newArr.length === 0) return [currElem];
			let element_with_same_value = newArr.find((e) => e.value === currElem.value);
			if (element_with_same_value) {
				element_with_same_value.description += `, ${currElem.description}`;
				return [...newArr];
			}
			return [...newArr, currElem];
		}, []);
		// returns [{value: 'Manufacturer 1', 'description': 'mobile part 1, mobile part 2'}]
	}

	toggle_href(doctype) {
		if (frappe.model.can_select(doctype) && !frappe.model.can_read(doctype)) {
			// remove href from link field as user has only select perm
			this.$input_area.find(".link-btn").addClass("hide");
		} else {
			this.$input_area.find(".link-btn").removeClass("hide");
		}
	}

	get_filter_description(filters) {
		let doctype = this.get_options();
		let filter_array = [];
		let meta = null;

		frappe.model.with_doctype(doctype, () => {
			meta = frappe.get_meta(doctype);
		});

		// convert object style to array
		if (!Array.isArray(filters)) {
			for (let fieldname in filters) {
				let value = filters[fieldname];
				if (!Array.isArray(value)) {
					value = ["=", value];
				}
				filter_array.push([fieldname, ...value]); // fieldname, operator, value
			}
		} else {
			filter_array = filters;
		}

		// add doctype if missing
		filter_array = filter_array.map((filter) => {
			if (filter.length === 3) {
				return [doctype, ...filter]; // doctype, fieldname, operator, value
			}
			return filter;
		});

		function get_filter_description(filter) {
			let doctype = filter[0];
			let fieldname = filter[1];
			let docfield = frappe.meta.get_docfield(doctype, fieldname);
			let label = docfield ? docfield.label : frappe.model.unscrub(fieldname);

			if (docfield && docfield.fieldtype === "Check") {
				filter[3] = filter[3] ? __("Yes") : __("No");
			}

			if (filter[3] && Array.isArray(filter[3]) && filter[3].length > 5) {
				filter[3] = filter[3].slice(0, 5);
				filter[3].push("...");
			}

			let value = filter[3] == null || filter[3] === "" ? __("empty") : String(filter[3]);

			return [__(label).bold(), __(filter[2]), value.bold()].join(" ");
		}

		let filter_string = filter_array.map(get_filter_description).join(", ");

		return __("Filters applied for {0}", [filter_string]);
	}

	set_custom_query(args) {
		const is_valid_value = (value, key) => {
			if (value) return true;
			// check if empty value is valid
			if (this.frm) {
				let field = frappe.meta.get_docfield(this.frm.doctype, key);
				// empty value link fields is invalid
				return !field || !["Link", "Dynamic Link"].includes(field.fieldtype);
			} else {
				return value !== undefined;
			}
		};

		const set_nulls = (obj) => {
			$.each(obj, (key, value) => {
				if (!is_valid_value(value, key)) {
					delete obj[key];
				}
			});
			return obj;
		};
		if (this.get_query || this.df.get_query) {
			var get_query = this.get_query || this.df.get_query;
			if ($.isPlainObject(get_query)) {
				var filters = null;
				if (get_query.filters) {
					// passed as {'filters': {'key':'value'}}
					filters = get_query.filters;
				} else if (get_query.query) {
					// passed as {'query': 'path.to.method'}
					args.query = get_query;
				} else {
					// dict is filters
					filters = get_query;
				}

				if (filters) {
					filters = set_nulls(filters);

					// extend args for custom functions
					$.extend(args, filters);

					// add "filters" for standard query (search.py)
					args.filters = filters;
				}
			} else if (typeof get_query === "string") {
				args.query = get_query;
			} else {
				// get_query by function
				var q = get_query(
					(this.frm && this.frm.doc) || this.doc,
					this.doctype,
					this.docname
				);

				if (typeof q === "string") {
					// returns a string
					args.query = q;
				} else if ($.isPlainObject(q)) {
					// returns a plain object with filters
					if (q.filters) {
						set_nulls(q.filters);
					}

					// turn off value translation
					if (q.translate_values !== undefined) {
						this.translate_values = q.translate_values;
					}

					// extend args for custom functions
					$.extend(args, q);

					// add "filters" for standard query (search.py)
					args.filters = q.filters;
				}
			}
		}
		if (this.df.filters) {
			set_nulls(this.df.filters);
			if (!args.filters) args.filters = {};
			$.extend(args.filters, this.df.filters);
		}
	}
	validate(value) {
		// validate the value just entered
		if (this._validated || this.df.options == "[Select]" || this.df.ignore_link_validation) {
			return value;
		}

		return this.validate_link_and_fetch(this.df, this.get_options(), this.docname, value);
	}
	validate_link_and_fetch(df, options, docname, value) {
		if (!options) return;

		const fetch_map = this.fetch_map;
		const columns_to_fetch = Object.values(fetch_map);

		// if default and no fetch, no need to validate
		if (!columns_to_fetch.length && df.__default_value === value) {
			return value;
		}

		function update_dependant_fields(response) {
			let field_value = "";
			for (const [target_field, source_field] of Object.entries(fetch_map)) {
				if (value) field_value = response[source_field];
				let target_df = frappe.meta.get_docfield(df.parent, target_field);
				let target_value = frappe.model.get_value(df.parent, docname, target_field);
				if (target_df?.fetch_if_empty && target_value) {
					continue;
				} else {
					frappe.model.set_value(
						df.parent,
						docname,
						target_field,
						field_value,
						df.fieldtype
					);
				}
			}
		}

		// to avoid unnecessary request
		if (value) {
			return frappe
				.xcall("frappe.client.validate_link", {
					doctype: options,
					docname: value,
					fields: columns_to_fetch,
				})
				.then((response) => {
					if (!docname || !columns_to_fetch.length) return response.name;
					update_dependant_fields(response);
					return response.name;
				});
		} else {
			update_dependant_fields({});
			return value;
		}
	}

	get fetch_map() {
		const fetch_map = {};
		if (!this.frm) return fetch_map;

		for (const key of ["*", this.df.parent]) {
			if (this.frm.fetch_dict[key] && this.frm.fetch_dict[key][this.df.fieldname]) {
				Object.assign(fetch_map, this.frm.fetch_dict[key][this.df.fieldname]);
			}
		}

		return fetch_map;
	}
};

if (Awesomplete) {
	Awesomplete.prototype.get_item = function (value) {
		return this._list.find(function (item) {
			return item.value === value;
		});
	};
}
