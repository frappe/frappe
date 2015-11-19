// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.make_control = function (opts) {
	var control_class_name = "Control" + opts.df.fieldtype.replace(/ /g, "");
	if(frappe.ui.form[control_class_name]) {
		return new frappe.ui.form[control_class_name](opts);
	} else {
		console.log("Invalid Control Name: " + opts.df.fieldtype);
	}
}

frappe.ui.form.Control = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();

		// if developer_mode=1, show fieldname as tooltip
		if(frappe.boot.user && frappe.boot.user.name==="Administrator" &&
			frappe.boot.developer_mode===1 && this.$wrapper) {
				this.$wrapper.attr("title", __(this.df.fieldname));
		}

		if(this.render_input) {
			this.refresh();
		}
	},
	make: function() {
		this.make_wrapper();
		this.$wrapper
			.attr("data-fieldtype", this.df.fieldtype)
			.attr("data-fieldname", this.df.fieldname);
		this.wrapper = this.$wrapper.get(0);
		this.wrapper.fieldobj = this; // reference for event handlers
	},

	make_wrapper: function() {
		this.$wrapper = $("<div class='frappe-control'></div>").appendTo(this.parent);
	},

	toggle: function(show) {
		this.df.hidden = show ? 0 : 1;
		this.refresh();
	},

	// returns "Read", "Write" or "None"
	// as strings based on permissions
	get_status: function(explain) {
		if(!this.doctype && !this.docname) {
			if (cint(this.df.hidden)) {
				if(explain) console.log("By Hidden: None");
				return "None";
			}

			return "Write";
		}

		var status = frappe.perm.get_field_display_status(this.df,
			frappe.model.get_doc(this.doctype, this.docname), this.perm || (this.frm && this.frm.perm), explain);

		// hide if no value
		if (this.doctype && status==="Read"
			&& is_null(frappe.model.get_value(this.doctype, this.docname, this.df.fieldname))
			&& !in_list(["HTML"], this.df.fieldtype)) {
				if(explain) console.log("By Hide Read-only, null fields: None");
				status = "None";
		}

		return status;
	},
	refresh: function() {
		this.disp_status = this.get_status();
		this.$wrapper
			&& this.$wrapper.toggleClass("hide-control", this.disp_status=="None")
			&& this.$wrapper.trigger("refresh");
	},
	get_doc: function() {
		return this.doctype && this.docname
			&& locals[this.doctype] && locals[this.doctype][this.docname] || {};
	},
	set_value: function(value) {
		this.parse_validate_and_set_in_model(value);
	},
	parse_validate_and_set_in_model: function(value) {
		var me = this;
		if(this.inside_change_event) return;
		this.inside_change_event = true;
		if(this.parse) value = this.parse(value);

		var set = function(value) {
			me.set_model_value(value);
			me.inside_change_event = false;
			me.set_mandatory && me.set_mandatory(value);
		}

		this.validate ? this.validate(value, set) : set(value);
	},
	get_parsed_value: function() {
		var me = this;
		return this.get_value ?
			(this.parse ? this.parse(this.get_value()) : this.get_value()) :
			undefined;
	},
	set_model_value: function(value) {
		if(frappe.model.set_value(this.doctype, this.docname, this.df.fieldname,
			value, this.df.fieldtype)) {
			this.last_value = value;
		}
	},
});

frappe.ui.form.ControlHTML = frappe.ui.form.Control.extend({
	make: function() {
		this._super();
		var me = this;
		this.disp_area = this.wrapper;
		this.$wrapper.on("refresh", function() {
			var content = me.get_content();
			if(content) me.$wrapper.html(content);
			return false;
		});
	},
	get_content: function() {
		return this.df.options || "";
	},
	html: function(html) {
		this.$wrapper.html(html || this.get_content());
	},
	set_value: function(html) {
		if(html.appendTo) {
			// jquery object
			html.appendTo(this.$wrapper.empty());
		} else {
			// html
			this.df.options = html;
			this.html(html);
		}
	}
});

frappe.ui.form.ControlHeading = frappe.ui.form.ControlHTML.extend({
	get_content: function() {
		return "<h4>" + __(this.df.label) + "</h4>";
	}
});

frappe.ui.form.ControlImage = frappe.ui.form.Control.extend({
	make: function() {
		this._super();
		var me = this;
		this.$wrapper.css({"margin": "0px"});
		this.$body = $("<div></div>").appendTo(this.$wrapper)
			.css({"margin-bottom": "10px"})
		this.$wrapper.on("refresh", function() {
				var doc = null;
				me.$body.empty();

				var doc = me.get_doc();
				if(doc && me.df.options && doc[me.df.options]) {
					me.$img = $("<img src='"+doc[me.df.options]+"' class='img-responsive'>")
						.appendTo(me.$body);
				} else {
					me.$buffer = $("<div class='missing-image'><i class='octicon octicon-circle-slash'></i></div>")
						.appendTo(me.$body)
				}
				return false;
			});
		$('<div class="clearfix"></div>').appendTo(this.$wrapper);
	}
});

frappe.ui.form.ControlInput = frappe.ui.form.Control.extend({
	horizontal: true,
	make: function() {
		// parent element
		this._super();
		this.set_input_areas();

		// set description
		this.set_max_width();
		this.setup_update_on_refresh();
	},
	make_wrapper: function() {
		if(this.only_input) {
			this.$wrapper = $('<div class="form-group frappe-control">').appendTo(this.parent);
		} else {
			this.$wrapper = $('<div class="frappe-control">\
				<div class="form-group" style="margin: 0px">\
					<label class="control-label" style="padding-right: 0px;"></label>\
					<div class="control-input-wrapper">\
						<div class="control-input"></div>\
						<div class="control-value like-disabled-input" style="display: none;"></div>\
						<p class="help-box small text-muted hidden-xs"></p>\
					</div>\
				</div>\
			</div>').appendTo(this.parent);
		}
	},
	toggle_label: function(show) {
		this.$wrapper.find(".control-label").toggleClass("hide", !show);
	},
	toggle_description: function(show) {
		this.$wrapper.find(".help-box").toggleClass("hide", !show);
	},
	set_input_areas: function() {
		if(this.only_input) {
			this.input_area = this.wrapper;
		} else {
			this.label_area = this.label_span = this.$wrapper.find("label").get(0);
			this.input_area = this.$wrapper.find(".control-input").get(0);
			// keep a separate display area to rendered formatted values
			// like links, currencies, HTMLs etc.
			this.disp_area = this.$wrapper.find(".control-value").get(0);
		}
	},
	set_max_width: function() {
		if(this.horizontal) {
			this.$wrapper.addClass("input-max-width");
		}
	},

	// update input value, label, description
	// display (show/hide/read-only),
	// mandatory style on refresh
	setup_update_on_refresh: function() {
		var me = this;
		this.$wrapper.on("refresh", function() {
			if(me.disp_status != "None") {
				// refresh value
				if(me.doctype && me.docname) {
					me.value = frappe.model.get_value(me.doctype, me.docname, me.df.fieldname);
				}

				if(me.disp_status=="Write") {
					me.disp_area && $(me.disp_area).toggle(false);
					$(me.input_area).toggle(true);
					$(me.input_area).find("input").prop("disabled", false);
					if(!me.has_input) {
						me.make_input();
						if(me.df.on_make) {
							me.df.on_make(me);
						}
					};
					if(me.doctype && me.docname) {
						me.set_input(me.value);
					} else {
						me.set_input(me.value || null);
					}
				} else {
					$(me.input_area).toggle(false);
					$(me.input_area).find("input").prop("disabled", true);
					if (me.disp_area) {
						me.set_disp_area();
						$(me.disp_area).toggle(true);
					}
				}

				me.set_description();
				me.set_label();
				me.set_mandatory(me.value);
				me.set_bold();
			}
			return false;
		});
	},

	set_disp_area: function() {
		this.disp_area && $(this.disp_area)
			.html(frappe.format(this.value, this.df, {no_icon:true, inline:true},
					this.doc || (this.frm && this.frm.doc)));
	},

	bind_change_event: function() {
		var me = this;
		this.$input && this.$input.on("change", this.change || function(e) {
			if(me.df.change) {
				// onchange event specified in df
				me.df.change.apply(this, e);
				return;
			}
			if(me.doctype && me.docname && me.get_value) {
				me.parse_validate_and_set_in_model(me.get_value());
			} else {
				// inline
				var value = me.get_value();
				var parsed = me.parse ? me.parse(value) : value;
				var set_input = function(before, after) {
					if(before !== after) {
						me.set_input(after);
					} else {
						me.set_mandatory && me.set_mandatory(before);
					}
				}
				if(me.validate) {
					me.validate(parsed, function(validated) {
						set_input(value, validated);
					});
				} else {
					set_input(value, parsed);
				}
			}
		});
	},
	bind_focusout: function() {
		// on touchscreen devices, scroll to top
		// so that static navbar and page head don't overlap the input
		if (frappe.dom.is_touchscreen()) {
			var me = this;
			this.$input && this.$input.on("focusout", function() {
				if (frappe.dom.is_touchscreen()) {
					frappe.ui.scroll(me.$wrapper);
				}
			});
		}
	},
	set_label: function(label) {
		if(label) this.df.label = label;

		if(this.only_input || this.df.label==this._label)
			return;

		var icon = "";
		this.label_span.innerHTML = (icon ? '<i class="'+icon+'"></i> ' : "") +
			__(this.df.label)  || "&nbsp;";
		this._label = this.df.label;
	},
	set_description: function() {
		if(this.only_input || this.df.description===this._description)
			return;
		if(this.df.description) {
			this.$wrapper.find(".help-box").html(__(this.df.description));
		} else {
			this.set_empty_description();
		}
		this._description = this.df.description;
	},
	set_empty_description: function() {
		this.$wrapper.find(".help-box").html("");
	},
	set_mandatory: function(value) {
		this.$wrapper.toggleClass("has-error", (this.df.reqd && is_null(value)) ? true : false);
	},
	set_bold: function() {
		if(this.$input) {
			this.$input.toggleClass("bold", !!this.df.bold);
		}
		if(this.disp_area) {
			$(this.disp_area).toggleClass("bold", !!this.df.bold);
		}
	}
});

frappe.ui.form.ControlData = frappe.ui.form.ControlInput.extend({
	html_element: "input",
	input_type: "text",
	make_input: function() {
		this.$input = $("<"+ this.html_element +">")
			.attr("type", this.input_type)
			.addClass("input-with-feedback form-control")
			.prependTo(this.input_area)

		if (in_list(['Data', 'Link', 'Dynamic Link', 'Password', 'Select', 'Read Only', 'Attach', 'Attach Image'],
			this.df.fieldtype)) {
				this.$input.attr("maxlength", this.df.length || 140);
		}

		this.set_input_attributes();
		this.input = this.$input.get(0);
		this.has_input = true;
		this.bind_change_event();
		this.bind_focusout();
	},
	set_input_attributes: function() {
		this.$input
			.attr("data-fieldtype", this.df.fieldtype)
			.attr("data-fieldname", this.df.fieldname)
			.attr("placeholder", this.df.placeholder || "")
		if(this.doctype) {
			this.$input.attr("data-doctype", this.doctype);
		}
		if(this.df.input_css) {
			this.$input.css(this.df.input_css);
		}
		if(this.df.input_class) {
			this.$input.addClass(this.df.input_class);
		}
	},
	set_input: function(val) {
		this.$input && this.$input.val(this.format_for_input(val));
		this.set_disp_area();
		this.last_value = val;
		this.set_mandatory && this.set_mandatory(val);
	},
	get_value: function() {
		return this.$input ? this.$input.val() : undefined;
	},
	format_for_input: function(val) {
		return val==null ? "" : val;
	},
	validate: function(v, callback) {
		if(this.df.options == 'Phone') {
			if(v+''=='') {
				callback("");
				return;
			}
			v1 = ''
			// phone may start with + and must only have numbers later, '-' and ' ' are stripped
			v = v.replace(/ /g, '').replace(/-/g, '').replace(/\(/g, '').replace(/\)/g, '');

			// allow initial +,0,00
			if(v && v.substr(0,1)=='+') {
				v1 = '+'; v = v.substr(1);
			}
			if(v && v.substr(0,2)=='00') {
				v1 += '00'; v = v.substr(2);
			}
			if(v && v.substr(0,1)=='0') {
				v1 += '0'; v = v.substr(1);
			}
			v1 += cint(v) + '';
			callback(v1);
		} else if(this.df.options == 'Email') {
			if(v+''=='') {
				callback("");
				return;
			}
			if(!validate_email(v)) {
				msgprint(__("Invalid Email: {0}", [v]));
					callback("");
			} else
				callback(v);
		} else {
			callback(v);
		}
	}
});

frappe.ui.form.ControlReadOnly = frappe.ui.form.ControlData.extend({
	get_status: function(explain) {
		var status = this._super(explain);
		if(status==="Write")
			status = "Read";
		return;
	},
});


frappe.ui.form.ControlPassword = frappe.ui.form.ControlData.extend({
	input_type: "password"
});

frappe.ui.form.ControlInt = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this._super();
		this.$input
			.addClass("text-right")
			.on("focus", function() {
				setTimeout(function() {
					if(!document.activeElement) return;
					me.validate(document.activeElement.value, function(val) {
						document.activeElement.value = val;
					});
					document.activeElement.select()
				}, 100);
				return false;
			})
	},
	parse: function(value) {
		return cint(value, null);
	},
	validate: function(value, callback) {
		return callback(value);
	}
});

frappe.ui.form.ControlFloat = frappe.ui.form.ControlInt.extend({
	parse: function(value) {
		return isNaN(parseFloat(value)) ? null : flt(value, this.get_precision());
	},

	format_for_input: function(value) {
		var number_format;
		if (this.df.fieldtype==="Float" && this.df.options && this.df.options.trim()) {
			number_format = this.get_number_format();
		}
		var formatted_value = format_number(parseFloat(value), number_format, this.get_precision());
		return isNaN(parseFloat(value)) ? "" : formatted_value;
	},

	// even a float field can be formatted based on currency format instead of float format
	get_number_format: function() {
		var currency = frappe.meta.get_field_currency(this.df, this.get_doc());
		return get_number_format(currency);
	},

	get_precision: function() {
		// round based on field precision or float precision, else don't round
		return this.df.precision || cint(frappe.boot.sysdefaults.float_precision, null);
	}
});

frappe.ui.form.ControlCurrency = frappe.ui.form.ControlFloat.extend({
	format_for_input: function(value) {
		var formatted_value = format_number(parseFloat(value), this.get_number_format(), this.get_precision());
		return isNaN(parseFloat(value)) ? "" : formatted_value;
	},

	get_precision: function() {
		// always round based on field precision or currency's precision
		// this method is also called in this.parse()
		if (!this.df.precision) {
			this.df.precision = get_number_format_info(this.get_number_format()).precision;
		}

		return this.df.precision;
	}
});

frappe.ui.form.ControlPercent = frappe.ui.form.ControlFloat;

frappe.ui.form.ControlDate = frappe.ui.form.ControlData.extend({
	datepicker_options: {
		altFormat:'yy-mm-dd',
		changeYear: true,
		yearRange: "-70Y:+10Y",
	},
	make_input: function() {
		this._super();
		this.set_datepicker();
	},
	set_datepicker: function() {
		this.datepicker_options.dateFormat =
			(frappe.boot.sysdefaults.date_format || 'yyyy-mm-dd').replace("yyyy", "yy")
		this.$input.datepicker(this.datepicker_options);
	},
	parse: function(value) {
		if(value) {
			value = dateutil.user_to_str(value);
		}
		return value;
	},
	format_for_input: function(value) {
		if(value) {
			value = dateutil.str_to_user(value);
		}
		return value || "";
	},
	validate: function(value, callback) {
		if(!dateutil.validate(value)) {
			if(value) {
				msgprint (__("Date must be in format: {0}", [sys_defaults.date_format || "yyyy-mm-dd"]));
			}
			callback("");
			return;
		}
		return callback(value);
	}
})

import_timepicker = function() {
	frappe.require("assets/frappe/js/lib/jquery/jquery.ui.slider.min.js");
	frappe.require("assets/frappe/js/lib/jquery/jquery.ui.sliderAccess.js");
	frappe.require("assets/frappe/js/lib/jquery/jquery.ui.timepicker-addon.css");
	frappe.require("assets/frappe/js/lib/jquery/jquery.ui.timepicker-addon.js");
}

frappe.ui.form.ControlTime = frappe.ui.form.ControlData.extend({
	make_input: function() {
		import_timepicker();
		this._super();
		this.$input.timepicker({
			timeFormat: 'HH:mm:ss',
		});
	}
});

frappe.ui.form.ControlDatetime = frappe.ui.form.ControlDate.extend({
	set_datepicker: function() {
		var now = new Date();
		$.extend(this.datepicker_options, {
			"timeFormat": "HH:mm:ss",
			"dateFormat": (frappe.boot.sysdefaults.date_format || 'yy-mm-dd').replace('yyyy','yy'),
			"hour": now.getHours(),
			"minute": now.getMinutes()
		});

		this.$input.datetimepicker(this.datepicker_options);
	},
	make_input: function() {
		import_timepicker();
		this._super();
	},
	parse: function(value) {
		if(value) {
			// parse and convert
			value = dateutil.convert_to_system_tz(dateutil.user_to_str(value));
		}
		return value;
	},
	format_for_input: function(value) {
		if(value) {
			// convert and format
			value = dateutil.str_to_user(dateutil.convert_to_user_tz(value));

		}
		return value || "";
	},

});

frappe.ui.form.ControlText = frappe.ui.form.ControlData.extend({
	html_element: "textarea",
	horizontal: false,
	make_wrapper: function() {
		this._super();
		this.$wrapper.find(".like-disabled-input").addClass("for-description");
	}
});

frappe.ui.form.ControlLongText = frappe.ui.form.ControlText;
frappe.ui.form.ControlSmallText = frappe.ui.form.ControlText;

frappe.ui.form.ControlCheck = frappe.ui.form.ControlData.extend({
	input_type: "checkbox",
	make_wrapper: function() {
		this.$wrapper = $('<div class="form-group frappe-control">\
			<div class="checkbox">\
				<label>\
					<span class="input-area"></span>\
					<span class="disp-area" style="display:none; margin-left: -20px;"></span>\
					<span class="label-area small"></span>\
				</label>\
				<p class="help-box small text-muted"></p>\
			</div>\
		</div>').appendTo(this.parent)
	},
	set_input_areas: function() {
		this.label_area = this.label_span = this.$wrapper.find(".label-area").get(0);
		this.input_area = this.$wrapper.find(".input-area").get(0);
		this.disp_area = this.$wrapper.find(".disp-area").get(0);
	},
	make_input: function() {
		this._super();
		this.$input.removeClass("form-control");
	},
	parse: function(value) {
		return this.input.checked ? 1 : 0;
	},
	validate: function(value, callback) {
		return callback(cint(value));
	},
	set_input: function(value) {
		this.input.checked = value ? 1 : 0;
		this.last_value = value;
	}
});

frappe.ui.form.ControlButton = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this.$input = $('<button class="btn btn-default btn-xs">')
			.prependTo(me.input_area)
			.on("click", function() {
				me.onclick();
			});
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;
		this.toggle_label(false);
	},
	onclick: function() {
		if(this.frm && this.frm.doc) {
			if(this.frm.script_manager.get_handlers(this.df.fieldname, this.doctype, this.docname).length) {
				this.frm.script_manager.trigger(this.df.fieldname, this.doctype, this.docname);
			} else {
				this.frm.runscript(this.df.options, this);
			}
		}
		else if(this.df.click) {
			this.df.click();
		}
	},
	set_input_areas: function() {
		this._super();
		$(this.disp_area).removeClass().addClass("hide");
	},
	set_empty_description: function() {
		this.$wrapper.find(".help-box").empty().toggle(false);
	},
	set_label: function() {
		$(this.label_span).html("&nbsp;");
		this.$input && this.$input.html((this.df.icon ?
			('<i class="'+this.df.icon+' icon-fixed-width"></i> ') : "") + __(this.df.label));
	}
});

frappe.ui.form.ControlAttach = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this.$input = $('<button class="btn btn-default btn-sm btn-attach">')
			.html(__("Attach"))
			.prependTo(me.input_area)
			.on("click", function() {
				me.onclick();
			});
		this.$value = $('<div style="margin-top: 5px;">\
			<div class="text-ellipsis" style="display: inline-block; width: 90%;">\
				<i class="icon-paper-clip"></i> \
				<a class="attached-file" target="_blank"></a>\
			</div>\
			<a class="close">&times;</a></div>')
			.prependTo(me.input_area)
			.toggle(false);
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;

		this.$value.find(".close").on("click", function() {
			if(me.frm) {
				me.frm.attachments.remove_attachment_by_filename(me.value, function() {
					me.parse_validate_and_set_in_model(null);
					me.refresh();
				});
			} else {
				me.dataurl = null;
				me.fileobj = null;
				me.set_input(null);
				me.refresh();
			}
		})
	},
	onclick: function() {
		if(this.doc) {
			var doc = this.doc.parent && frappe.model.get_doc(this.doc.parenttype, this.doc.parent) || this.doc;
			if (doc.__islocal) {
				frappe.msgprint(__("Please save the document before uploading."));
				return;
			}
		}
		if(!this.dialog) {
			this.dialog = new frappe.ui.Dialog({
				title: __(this.df.label || __("Upload")),
				fields: [
					{fieldtype:"HTML", fieldname:"upload_area"},
					{fieldtype:"HTML", fieldname:"or_attach", options: __("Or")},
					{fieldtype:"Select", fieldname:"select", label:__("Select from existing attachments") },
				]
			});
		}

		this.dialog.show();

		this.dialog.get_field("upload_area").$wrapper.empty();

		// select from existing attachments
		var attachments = this.frm && this.frm.attachments.get_attachments() || [];
		var select = this.dialog.get_field("select");
		if(attachments.length) {
			attachments = $.map(attachments, function(o) { return o.file_url; })
			select.df.options = [""].concat(attachments);
			select.toggle(true);
			this.dialog.get_field("or_attach").toggle(true);
			select.refresh();
		} else {
			this.dialog.get_field("or_attach").toggle(false);
			select.toggle(false);
		}
		select.$input.val("");

		this.set_upload_options();
		frappe.upload.make(this.upload_options);
	},

	set_upload_options: function() {
		var me = this;
		this.upload_options = {
			parent: this.dialog.get_field("upload_area").$wrapper,
			args: {},
			max_width: this.df.max_width,
			max_height: this.df.max_height,
			options: this.df.options,
			btn: this.dialog.set_primary_action(__("Upload")),
			on_no_attach: function() {
				// if no attachmemts,
				// check if something is selected
				var selected = me.dialog.get_field("select").get_value();
				if(selected) {
					me.parse_validate_and_set_in_model(selected);
					me.dialog.hide();
				} else {
					msgprint(__("Please attach a file or set a URL"));
				}
			},
			callback: function(attachment, r) {
				me.on_upload_complete(attachment);
				me.dialog.hide();
			},
			onerror: function() {
				me.dialog.hide();
			},
		}

		if(this.frm) {
			this.upload_options.args = {
				from_form: 1,
				doctype: this.frm.doctype,
				docname: this.frm.docname,
			}
		} else {
			this.upload_options.on_attach = function(fileobj, dataurl) {
				me.dialog.hide();
				me.fileobj = fileobj;
				me.dataurl = dataurl;
				if(me.on_attach) {
					me.on_attach()
				}
				if(me.df.on_attach) {
					me.df.on_attach(fileobj, dataurl);
				}
				me.on_upload_complete();
			}
		}
	},

	set_input: function(value, dataurl) {
		this.value = value;
		if(this.value) {
			this.$input.toggle(false);
			if(this.value.indexOf(",")!==-1) {
				var parts = this.value.split(",");
				var filename = parts[0];
				var dataurl = parts[1];
			}
			this.$value.toggle(true).find(".attached-file")
				.html(filename || this.value)
				.attr("href", dataurl || this.value);
		} else {
			this.$input.toggle(true);
			this.$value.toggle(false);
		}
	},

	get_value: function() {
		if(this.frm) {
			return this.value;
		} else {
			return this.fileobj ? (this.fileobj.filename + "," + this.dataurl) : null;
		}
	},

	on_upload_complete: function(attachment) {
		if(this.frm) {
			this.parse_validate_and_set_in_model(attachment.file_url);
			this.refresh();
			this.frm.attachments.update_attachment(attachment);
		} else {
			this.value = this.get_value();
			this.refresh();
		}
	},
});

frappe.ui.form.ControlAttachImage = frappe.ui.form.ControlAttach.extend({
	make_input: function() {
		var me = this;
		this._super();
		this.img_wrapper = $('<div style="margin: 7px 0px;">\
			<div class="missing-image attach-missing-image"><i class="octicon octicon-circle-slash"></i></div></div>')
			.prependTo(this.input_area);
		this.img = $("<img class='img-responsive attach-image-display'>")
			.appendTo(this.img_wrapper).toggle(false);

		// propagate click to Attach button
		this.img_wrapper.find(".missing-image").on("click", function() { me.$input.click(); });
		this.img.on("click", function() { me.$input.click(); });

		this.$wrapper.on("refresh", function() {
			me.set_image();
		});
		
		this.set_image();
	},
	set_image: function() {
		if(this.get_value()) {
			$(this.input_area).find(".missing-image").toggle(false);
			this.img.attr("src", this.dataurl ? this.dataurl : this.value).toggle(true);
		} else {
			$(this.input_area).find(".missing-image").toggle(true);
			this.img.toggle(false);
		}
	}
});


frappe.ui.form.ControlSelect = frappe.ui.form.ControlData.extend({
	html_element: "select",
	make_input: function() {
		var me = this;
		this._super();
		this.set_options();
	},
	set_input: function(value) {
		// refresh options first - (new ones??)
		this.set_options(value || "");

		this._super(value);

		var input_value = this.$input.val();

		// not a possible option, repair
		if(this.doctype && this.docname) {
			// model value is not an option,
			// set the default option (displayed)
			var model_value = frappe.model.get_value(this.doctype, this.docname, this.df.fieldname);
			if(model_value == null && (input_value || "") != (model_value || "")) {
				this.set_model_value(input_value);
			} else {
				this.last_value = value;
			}
		} else {
			if(value !== input_value) {
				this.set_value(input_value);
			}
		}
	},
	set_options: function(value) {
		var options = this.df.options || [];
		if(typeof this.df.options==="string") {
			options = this.df.options.split("\n");
		}
		if(this.in_filter && options[0] != "") {
			options = add_lists([''], options);
		}

		// nothing changed
		if(options.toString() === this.last_options) {
			return;
		}
		this.last_options = options.toString();

		var selected = this.$input.find(":selected").val();
		this.$input.empty().add_options(options || []);

		if(value===undefined && selected) {
			this.$input.val(selected);
		}
	},
	get_file_attachment_list: function() {
		if(!this.frm) return;
		var fl = frappe.model.docinfo[this.frm.doctype][this.frm.docname];
		if(fl && fl.attachments) {
			this.set_description("");
			var options = [""];
			$.each(fl.attachments, function(i, f) {
				options.push(f.file_url)
			});
			return options;
		} else {
			this.set_description(__("Please attach a file first."))
			return [""];
		}
	}
});

// special features for link
// buttons
// autocomplete
// link validation
// custom queries
// add_fetches
frappe.ui.form.ControlLink = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		$('<div class="link-field ui-front" style="position: relative;">\
			<input type="text" class="input-with-feedback form-control">\
			<span class="link-btn">\
				<a class="btn-open no-decoration" title="' + __("Open Link") + '">\
					<i class="icon-link"></i></a>\
			</span>\
		</div>').prependTo(this.input_area);
		this.$input_area = $(this.input_area);
		this.$input = this.$input_area.find('input');
		this.$link = this.$input_area.find('.link-btn');
		this.set_input_attributes();
		this.$input.on("focus", function() {
			me.$link.toggle(true);
			setTimeout(function() {
				if(!me.$input.val()) {
					me.$input.autocomplete("search", "");
				}
			}, 500);
		});
		this.$input.on("blur", function() {
			setTimeout(function() { me.$link.toggle(false); }, 500);
		});
		this.input = this.$input.get(0);
		this.has_input = true;
		var me = this;
		this.setup_buttons();
		this.setup_autocomplete();
		if(this.df.change) {
			this.$input.on("change", function() {
				me.df.change.apply(this);
			});
		}
	},
	get_options: function() {
		return this.df.options;
	},
	setup_buttons: function() {
		var me = this;

		// open
		this.$input_area.find(".btn-open").on("click", function() {
			var value = me.get_value();
			if(value && me.get_options())
				frappe.set_route("Form", me.get_options(), value);
		});

		if(this.only_input) this.$input_area.find(".link-btn").remove();
	},
	open_advanced_search: function() {
		var doctype = this.get_options();
		if(!doctype) return;
		new frappe.ui.form.LinkSelector({
			doctype: doctype,
			target: this,
			txt: this.get_value()
		});
		return false;
	},
	new_doc: function() {
		var doctype = this.get_options();
		if(!doctype) return;
		var new_options = { "name_field": this.get_value() };

		if(this.df.get_route_options_for_new_doc) {
			frappe.route_options = this.df.get_route_options_for_new_doc(this);
		}

		if(this.frm) {
			this.frm.new_doc(doctype, this, new_options);
		} else {
			new_doc(doctype, new_options);
		}
		return false;
	},
	setup_autocomplete: function() {
		var me = this;
		this.$input.on("blur", function() {
			if(me.selected) {
				me.selected = false;
				return;
			}
			if(me.doctype && me.docname) {
				var value = me.get_value();
				if(value!==me.last_value) {
					me.parse_validate_and_set_in_model(value);
				}
			}
		});

		this.$input.cache = {};
		this.$input.autocomplete({
			minLength: 0,
			autoFocus: true,
			source: function(request, response) {
				var doctype = me.get_options();
				if(!doctype) return;
				if (!me.$input.cache[doctype]) {
					me.$input.cache[doctype] = {};
				}

				if (me.$input.cache[doctype][request.term]!=null) {
					// immediately show from cache
					response(me.$input.cache[doctype][request.term]);
				}

				var args = {
					'txt': request.term,
					'doctype': doctype,
				};

				me.set_custom_query(args);

				return frappe.call({
					type: "GET",
					method:'frappe.desk.search.search_link',
					no_spinner: true,
					args: args,
					callback: function(r) {
						if(!me.df.only_select) {
							if(frappe.model.can_create(doctype)
								&& me.df.fieldtype !== "Dynamic Link") {
								// new item
								r.results.push({
									value: "<span class='text-primary link-option'>"
										+ "<i class='icon-plus' style='margin-right: 5px;'></i> "
										+ __("Create a new {0}", [__(me.df.options)])
										+ "</span>",
									action: me.new_doc
								});
							};
							// advanced search
							r.results.push({
								value: "<span class='text-primary link-option'>"
									+ "<i class='icon-search' style='margin-right: 5px;'></i> "
									+ __("Advanced Search")
									+ "</span>",
								action: me.open_advanced_search
							});
						}

						me.$input.cache[doctype][request.term] = r.results;
						response(r.results);
					},
				});
			},
			open: function(event, ui) {
				me.$wrapper.css({"z-index": 101});
				me.autocomplete_open = true;
			},
			close: function(event, ui) {
				me.$wrapper.css({"z-index": 1});
				me.autocomplete_open = false;
			},
			focus: function( event, ui ) {
				event.preventDefault();
				if(ui.item.action) {
					return false;
				}
			},
			select: function(event, ui) {
				me.autocomplete_open = false;
				if(ui.item.action) {
					ui.item.action.apply(me);
					return false;
				}

				if(me.frm && me.frm.doc) {
					me.selected = true;
					me.parse_validate_and_set_in_model(ui.item.value);
				} else {
					me.$input.val(ui.item.value);
					me.$input.trigger("change");
				}
			}
		}).data('ui-autocomplete')._renderItem = function(ul, d) {
			var html = "<strong>" + __(d.value) + "</strong>";
			if(d.description && d.value!==d.description) {
				html += '<br><span class="small">' + __(d.description) + '</span>';
			}
			return $('<li></li>')
				.data('item.autocomplete', d)
				.html('<a><p>' + html + '</p></a>')
				.appendTo(ul);
		};
		// remove accessibility span (for now)
		this.$wrapper.find(".ui-helper-hidden-accessible").remove();
	},
	set_custom_query: function(args) {
		var set_nulls = function(obj) {
			$.each(obj, function(key, value) {
				if(value!==undefined) {
					obj[key] = value;
				}
			});
			return obj;
		}
		if(this.get_query || this.df.get_query) {
			var get_query = this.get_query || this.df.get_query;
			if($.isPlainObject(get_query)) {
				var filters = set_nulls(get_query);

				// extend args for custom functions
				$.extend(args, filters);

				// add "filters" for standard query (search.py)
				args.filters = filters;
			} else if(typeof(get_query)==="string") {
				args.query = get_query;
			} else {
				var q = (get_query)(this.frm && this.frm.doc, this.doctype, this.docname);

				if (typeof(q)==="string") {
					args.query = q;
				} else if($.isPlainObject(q)) {
					if(q.filters) {
						set_nulls(q.filters);
					}
					// extend args for custom functions
					$.extend(args, q);

					// add "filters" for standard query (search.py)
					args.filters = q.filters;
				}
			}
		}
		if(this.df.filters) {
			set_nulls(this.df.filters);
			if(!args.filters) args.filters = {};
			$.extend(args.filters, this.df.filters);
		}
	},
	validate: function(value, callback) {
		// validate the value just entered
		var me = this;

		if(this.df.options=="[Select]") {
			callback(value);
			return;
		}

		this.frm.script_manager.validate_link_and_fetch(this.df, this.get_options(),
			this.docname, value, callback);
	},
});

frappe.ui.form.ControlDynamicLink = frappe.ui.form.ControlLink.extend({
	get_options: function() {
		if(this.df.get_options) {
			return this.df.get_options();
		}
		var options = frappe.model.get_value(this.df.parent, this.docname, this.df.options);
		if(!options) {
			msgprint(__("Please set {0} first",
				[frappe.meta.get_docfield(this.df.parent, this.df.options, this.docname).label]));
		}
		return options;
	},
});

frappe.ui.form.ControlCode = frappe.ui.form.ControlText.extend({
	make_input: function() {
		this._super();
		$(this.input_area).find("textarea").css({"height":"400px", "font-family": "Monaco, \"Courier New\", monospace"});
	}
});

frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	editor_name: "bsEditor",
	horizontal: false,
	make_input: function() {
		//$(this.input_area).css({"min-height":"360px"});
		this.has_input = true;
		this.make_rich_text_editor();
		this.make_markdown_editor();
		this.make_switcher();
	},
	make_rich_text_editor: function() {
		var me = this;
		this.editor_wrapper = $("<div>").appendTo(this.input_area);
		var onchange = function(value) {
			me.md_editor.val(value);
			me.parse_validate_and_set_in_model(value);
		}
		this.editor = new (frappe.provide(this.editor_name))({
			parent: this.editor_wrapper,
			change: onchange,
			field: this
		});
		this.editor.editor.on("blur", function() {
			onchange(me.editor.clean_html());
		});
		this.editor.editor.keypress("ctrl+s meta+s", function() {
			me.frm.save_or_update();
		});
	},
	make_markdown_editor: function() {
		var me = this;
		this.md_editor_wrapper = $("<div class='hide'>")
			.appendTo(this.input_area);
		this.md_editor = $("<textarea class='form-control markdown-text-editor'>")
		.appendTo(this.md_editor_wrapper)
		.allowTabs()
		.on("change", function() {
			var value = $(this).val();
			me.editor.set_input(value);
			me.parse_validate_and_set_in_model(value);
		});

		$('<div class="text-muted small">Add &lt;!-- markdown --&gt; \
			to always interpret as markdown</div>')
			.appendTo(this.md_editor_wrapper);
	},
	make_switcher: function() {
		var me = this;
		this.current_editor = this.editor;
		this.switcher = $('<p class="text-right small">\
			<a href="#" class="switcher"></a></p>')
			.appendTo(this.input_area)
			.find("a")
			.click(function() {
				me.switch();
				return false;
			});
		this.render_switcher();
	},
	switch: function() {
		if(this.current_editor===this.editor) {
			// switch to md
			var value = this.editor.get_value();
			this.editor_wrapper.addClass("hide");
			this.md_editor_wrapper.removeClass("hide");
			this.current_editor = this.md_editor;
			this.add_type_marker("markdown");
		} else {
			// switch to html
			var value = this.md_editor.val();
			this.md_editor_wrapper.addClass("hide");
			this.editor_wrapper.removeClass("hide");
			this.current_editor = this.editor;
			this.add_type_marker("html");
		}
		this.render_switcher();
	},
	add_type_marker: function(marker) {
		var opp_marker = marker==="html" ? "markdown" : "html";
		if(!this.value) this.value = "";
		if(this.value.indexOf("<!-- " + opp_marker + " -->")!==-1) {
			// replace opposite marker
			this.set_value(this.value.split("<!-- " + opp_marker + " -->").join("<!-- " + marker + " -->"));
		} else if(this.value.indexOf("<!-- " + marker + " -->")===-1) {
			// add marker (marker missing)
			this.set_value(this.value + "\n\n\n<!-- " + marker + " -->");
		}
	},
	render_switcher: function() {
		this.switcher.html(__("Edit as {0}", [this.current_editor == this.editor ?
			__("Markdown") : __("Rich Text")]));
	},
	get_value: function() {
		return this.current_editor === this.editor
			? this.editor.get_value()
			: this.md_editor.val();
	},
	set_input: function(value) {
		this._set_input(value);

		// guess editor type
		var is_markdown = false;
		if(value) {
			if(value.indexOf("<!-- markdown -->") !== -1) {
				var is_markdown = true;
			}
			if((is_markdown && this.current_editor===this.editor)
				|| (!is_markdown && this.current_editor===this.md_editor)) {
				this.switch();
			}
		}
	},
	_set_input: function(value) {
		if(value == null) value = "";
		value = frappe.utils.remove_script_and_style(value);
		this.editor.set_input(value);
		this.md_editor.val(value);
		this.last_value = value;
	}
});

frappe.ui.form.ControlTable = frappe.ui.form.Control.extend({
	make: function() {
		this._super();

		// add title if prev field is not column / section heading or html
		this.grid = new frappe.ui.form.Grid({
			frm: this.frm,
			df: this.df,
			perm: this.perm || this.frm.perm,
			parent: this.wrapper
		})
		if(this.frm)
			this.frm.grids[this.frm.grids.length] = this;

		// description
		if(this.df.description) {
			$('<p class="text-muted small">' + __(this.df.description) + '</p>')
				.appendTo(this.wrapper);
		}

		var me = this;
		this.$wrapper.on("refresh", function() {
			me.grid.refresh();
			return false;
		});
	}
})

frappe.ui.form.fieldtype_icons = {
	"Date": "icon-calendar",
	"Time": "icon-time",
	"Datetime": "icon-time",
	"Code": "icon-code",
	"Select": "icon-flag"
};
