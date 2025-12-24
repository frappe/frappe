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
				<a class="btn-open" tabIndex='-1' style="display: inline-block;" title="${__("Open Link")}">
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
			if (!me.$input.val()) {
				me.$input.val("");

				// Create a fake input event
				const e = $.Event("input");
				e.target = me.$input[0];

				// Pass it to on_input directly, bypassing debounce, so the dropdown opens immediately
				me.on_input(e);
			}

			me.show_link_and_clear_buttons();
		});
		this.$input.on("blur", function () {
			// if this disappears immediately, the user's click
			// does not register, hence timeout
			setTimeout(function () {
				me.$link.toggle(false);
				me.hide_link_and_clear_buttons();
			}, 250);
		});

		this.$input_area.on("mouseenter", () => {
			this.show_link_and_clear_buttons();
		});

		this.$input_area.on("mouseleave", () => {
			if (!this.$input.is(":focus")) {
				this.hide_link_and_clear_buttons();
			}
		});

		this.$input.attr("data-target", this.df.options);
		this.input = this.$input.get(0);
		this.has_input = true;
		this.translate_values = true;
		this.setup_buttons();
		this.setup_awesomeplete();
		this.bind_change_event();
	}

	show_link_and_clear_buttons() {
		if (this.$input.val() && this.get_options()) {
			const doctype = this.get_options();
			const name = this.get_input_value();
			this.$link.toggle(true);
			this.$link_open.attr("href", frappe.utils.get_form_link(doctype, name));
		}
	}

	hide_link_and_clear_buttons() {
		this.$link.toggle(false);
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
		super.set_formatted_input(value);
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
		return (frappe.boot?.translated_doctypes || []).includes(this.get_options());
	}
	is_title_link() {
		return (frappe.boot?.link_title_doctypes || []).includes(this.get_options());
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
		if (this.parse) value = this.parse(value);
		if (label) {
			this.label = this.get_translated(label);
			frappe.utils.add_link_title(this.get_options(), value, label);
		}

		return this.validate_and_set_in_model(value, e);
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
		frappe._from_link = {
			field_obj: this,
			from_doctype: this.doctype,
			from_docname: this.doc?.name,
			scrollY: $(document).scrollTop(),
		};

		frappe.ui.form.make_quick_entry(doctype, (doc) => {
			return me.set_value(doc.name);
		});

		return false;
	}
	setup_awesomeplete() {
		let me = this;

		this.$input.cache = {};

		this.awesomplete = new Awesomplete(me.input, {
			tabSelect: true,
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

				// Sanitize label and description before using them to build HTML
				let _label = frappe.utils.escape_html(me.get_translated(d.label));
				let html = d.html || "<strong>" + _label + "</strong>";
				if (
					d.description &&
					// for title links, we want to inlude the value in the description
					// because it will not visible otherwise
					(me.is_title_link() || d.value !== d.description)
				) {
					html +=
						'<br><span class="small">' +
						__(frappe.utils.escape_html(d.description)) +
						"</span>";
				}
				return $(`<div role="option">`)
					.on("click", (event) => {
						me.awesomplete.select(event.currentTarget, event.currentTarget);
						me.show_link_and_clear_buttons();
					})
					.data("item.autocomplete", d)
					.prop("aria-selected", "false")
					.html(`<p title="${frappe.utils.escape_html(_label)}">${html}</p>`)
					.get(0);
			},
			sort: function () {
				return 0;
			},
		});

		this.custom_awesomplete_filter && this.custom_awesomplete_filter(this.awesomplete);

		this.$input.on("input", frappe.utils.debounce(this.on_input.bind(this), 500));

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

			// prevent selection on tab/enter if input doesn't match
			const TABKEY = 9;
			const ENTERKEY = 13;
			const event = o.originalEvent;
			if (event && [TABKEY, ENTERKEY].includes(event.keyCode)) {
				const input = me.get_label_value().toLowerCase();
				if (!input && event.keyCode === TABKEY) {
					e.preventDefault();
					me.awesomplete.close();
					return false;
				} else if (input && !me.input_matches_item(input, item)) {
					e.preventDefault();

					// prevent browser default tab behavior (focus change)
					if (event.preventDefault) {
						event.preventDefault();
					}
					return false;
				}
			}

			if (item.value === "filter_description__link_option") {
				e.preventDefault();
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

	/**
	 * Checks if the current input matches any property (label, value, or description)
	 * of the provided autocomplete item (case-insensitive).
	 *
	 * @param {string} input - The current input value.
	 * @param {Object} item - The autocomplete item to check against.
	 * @returns {boolean} - True if input matches the label, value, or description.
	 */
	input_matches_item(input, item) {
		const item_label = (this.get_translated(item.label || item.value) || "").toLowerCase();
		const item_description = (item.description || "").toLowerCase();
		return input && (item_label.includes(input) || item_description.includes(input));
	}

	/**
	 * Determine if we should use GET (enables HTTP caching) or POST.
	 * Use GET for empty searches with filters that fit in URL.
	 * Use POST for searches with text or large filters.
	 */
	should_use_post_for_search(txt, filters, max_get_size = 2000) {
		// Always use POST if there's search text
		if (txt) return true;

		// If no filters, use GET
		if (!filters) return false;

		// Check size of filters when stringified
		let filters_str = filters;
		if (typeof filters !== "string") {
			try {
				filters_str = JSON.stringify(filters);
			} catch (e) {
				// If stringification fails, use POST
				return true;
			}
		}

		// URL-encoded params add ~30% overhead on average
		const estimated_size = filters_str.length * 1.3;
		return estimated_size > max_get_size;
	}

	on_input(e) {
		var doctype = this.get_options();
		if (!doctype) return;
		if (!this.$input.cache[doctype]) {
			this.$input.cache[doctype] = {};
		}

		var term = e.target.value;

		if (this.$input.cache[doctype][term] != null) {
			// immediately show from cache
			this.awesomplete.list = this.$input.cache[doctype][term];
		}
		var args = {
			txt: term,
			doctype: doctype,
			ignore_user_permissions: this.df.ignore_user_permissions,
			reference_doctype: this.get_reference_doctype() || "",
			page_length: cint(frappe.boot.sysdefaults?.link_field_results_limit) || 10,
			link_fieldname: this.df.fieldname,
		};

		this.set_custom_query(args);

		const use_get = !this.should_use_post_for_search(term, args.filters);
		frappe.call({
			type: use_get ? "GET" : "POST",
			method: "frappe.desk.search.search_link",
			no_spinner: true,
			cache: use_get,
			args: args,
			callback: (r) => {
				if (!window.Cypress && !this.$input.is(":focus")) {
					return;
				}
				r.message = this.merge_duplicates(r.message);

				// show filter description in awesomplete
				let filter_string = this.df.filter_description
					? this.df.filter_description
					: args.filters
					? this.get_filter_description(args.filters)
					: null;
				if (filter_string) {
					r.message.push({
						html: `<span class="text-muted" style="line-height: 1.5">${filter_string}</span>`,
						value: "filter_description__link_option",
						action: () => {},
					});
				}

				if (!this.df.only_select) {
					if (frappe.model.can_create(doctype)) {
						// new item
						r.message.push({
							html:
								"<span class='link-option'>" +
								"<i class='fa fa-plus' style='margin-right: 5px;'></i> " +
								__("Create a new {0}", [__(this.get_options())]) +
								"</span>",
							label: __("Create a new {0}", [__(this.get_options())]),
							value: "create_new__link_option",
							action: this.new_doc,
						});
					}

					//custom link actions
					let custom__link_options =
						frappe.ui.form.ControlLink.link_options &&
						frappe.ui.form.ControlLink.link_options(this);

					if (custom__link_options) {
						r.message = r.message.concat(custom__link_options);
					}

					// advanced search
					if (locals && locals["DocType"]) {
						// not applicable in web forms
						r.message.push({
							html:
								"<span class='link-option'>" +
								"<i class='fa fa-search' style='margin-right: 5px;'></i> " +
								__("Advanced Search") +
								"</span>",
							label: __("Advanced Search"),
							value: "advanced_search__link_option",
							action: this.open_advanced_search,
						});
					}
				}
				this.$input.cache[doctype][term] = r.message;
				this.awesomplete.list = this.$input.cache[doctype][term];
				this.toggle_href(doctype);
				r.message.forEach((item) => {
					frappe.utils.add_link_title(doctype, item.value, item.label);
				});
			},
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
				if (currElem.description) {
					element_with_same_value.description += `, ${currElem.description}`;
				}
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

			let value;
			if (filter[3] && Array.isArray(filter[3])) {
				value = filter[3].map((v) => String(__(v)).bold()).join(", ");
			} else if (filter[3] == null || filter[3] === "") {
				value = __("empty").bold();
			} else {
				value = String(__(filter[3])).bold();
			}

			return [__(label).bold(), __(filter[2]), value].join(" ");
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

		// apply link field filters
		if (this.df.link_filters && !!this.df.link_filters.length) {
			this.apply_link_field_filters();
		}

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

	apply_link_field_filters() {
		let link_filters = JSON.parse(this.df.link_filters);
		let filters = this.parse_filters(link_filters);
		// take filters from the link field and add to the query
		this.get_query = function () {
			return {
				filters,
			};
		};
	}

	parse_filters(link_filters) {
		let filters = {};
		link_filters.forEach((filter) => {
			let [_, fieldname, operator, value] = filter;
			if (value?.startsWith?.("eval:")) {
				// get the value to calculate
				value = value.split("eval:")[1];
				let context = {
					doc: this.doc,
					parent: this.doc.parenttype ? this.frm.doc : null,
					frappe,
				};
				value = frappe.utils.eval(value, context);
			}
			filters[fieldname] = [operator, value];
		});
		return filters;
	}

	validate(value) {
		// validate the value just entered
		if (this._validated || this.df.options == "[Select]" || this.df.ignore_link_validation) {
			return value;
		}

		return this.validate_link_and_fetch(value);
	}
	validate_link_and_fetch(value) {
		const options = this.get_options();
		if (!options) {
			return;
		}

		const columns_to_fetch = Object.values(this.fetch_map);
		const nothing_to_fetch = !columns_to_fetch.length;

		// if default and no fetch, no need to validate
		if (nothing_to_fetch && this.df.__default_value === value) {
			return value;
		}

		if (
			nothing_to_fetch &&
			value &&
			this.awesomplete?._list?.find((item) => item.value === value && !item.action)
		) {
			// if value is in the suggestion list, must be correct
			return value;
		}

		const update_dependant_fields = (response) => {
			let field_value = "";
			for (const [target_field, source_field] of Object.entries(this.fetch_map)) {
				if (value) {
					field_value = response[source_field];
				}

				if (this.layout?.set_value) {
					this.layout.set_value(target_field, field_value);
				} else if (this.frm) {
					frappe.model.set_value(
						this.df.parent,
						this.docname,
						target_field,
						field_value,
						this.df.fieldtype
					);
				}
			}
		};

		// to avoid unnecessary request
		if (value) {
			return frappe
				.xcall(
					"frappe.client.validate_link",
					{
						doctype: options,
						docname: value,
						fields: columns_to_fetch,
					},
					"GET",
					{ cache: !columns_to_fetch.length }
				)
				.then((response) => {
					if (this.frm && !this.docname) {
						return response.name;
					}
					if (!columns_to_fetch.length) {
						return response.name;
					}
					update_dependant_fields(response);
					return response.name;
				});
		} else {
			update_dependant_fields({});
			return value;
		}
	}

	fetch_map_for_quick_entry() {
		let me = this;
		let fetch_map = {};
		function add_fetch(link_field, source_field, target_field, target_doctype) {
			if (!target_doctype) target_doctype = "*";

			if (!me.layout.fetch_dict) {
				me.layout.fetch_dict = {};
			}

			// Target field kept as key because source field could be non-unique
			me.layout.fetch_dict.setDefault(target_doctype, {}).setDefault(link_field, {})[
				target_field
			] = source_field;
		}

		function setup_add_fetch(df) {
			let is_read_only_field =
				[
					"Data",
					"Read Only",
					"Text",
					"Small Text",
					"Currency",
					"Check",
					"Text Editor",
					"Attach Image",
					"Code",
					"Link",
					"Float",
					"Int",
					"Date",
					"Datetime",
					"Select",
					"Duration",
					"Time",
					"Percent",
					"Phone",
					"Barcode",
					"Autocomplete",
					"Icon",
					"Color",
					"Rating",
				].includes(df.fieldtype) ||
				df.read_only == 1 ||
				df.is_virtual == 1;

			if (is_read_only_field && df.fetch_from && df.fetch_from.indexOf(".") != -1) {
				var parts = df.fetch_from.split(".");
				add_fetch(parts[0], parts[1], df.fieldname, df.parent);
			}
		}

		$.each(this.layout.fields, (i, field) => setup_add_fetch(field));

		for (const key of ["*", this.df.parent]) {
			if (!this.layout.fetch_dict) {
				this.layout.fetch_dict = {};
			}
			if (this.layout.fetch_dict[key] && this.layout.fetch_dict[key][this.df.fieldname]) {
				Object.assign(fetch_map, this.layout.fetch_dict[key][this.df.fieldname]);
			}
		}

		return fetch_map;
	}

	get fetch_map() {
		const fetch_map = {};

		// Create fetch_map from quick entry fields
		if (!this.frm && this.layout && this.layout.fields) {
			return this.fetch_map_for_quick_entry();
		}

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
