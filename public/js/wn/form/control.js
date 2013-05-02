wn.ui.form.make_control = function(opts) {
	var control_class_name = "Control" + opts.df.fieldtype.replace(/ /g, "");
	if(wn.ui.form[control_class_name]) {
		return new wn.ui.form[control_class_name](opts);
	} else {
		console.log("Invalid Control Name: " + opts.df.fieldtype);
	}
}

wn.ui.form.Control = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		this.$wrapper = $("<div>").appendTo(this.parent);
		this.wrapper = this.$wrapper.get(0);
	},
	
	// returns "Read", "Write" or "None" 
	// as strings based on permissions
	get_status: function(explain) {
		if(!this.doctype) 
			return "Write";
		return wn.perm.get_field_display_status(this.df, 
			locals[this.doctype][this.docname], this.perm, explain);
	},
	refresh: function() {
		this.disp_status = this.get_status();
		this.$wrapper && this.$wrapper.toggle(this.disp_status!="None");
		this.$wrapper && this.$wrapper.trigger("refresh");
	},
	get_doc: function() {
		return this.doctype && this.docname 
			&& locals[this.doctype] && locals[this.doctype][this.docname] || {};
	}
});

wn.ui.form.ControlHTML = wn.ui.form.Control.extend({
	make: function() {
		this._super();
		var me = this;
		this.$wrapper.on("refresh", function() {
			if(me.df.options)
				me.$wrapper.html(me.df.options);
		})
	}
});

wn.ui.form.ControlReadOnly = wn.ui.form.Control.extend({
	make: function() {
		this._super();
		var me = this;
		this.$wrapper.on("refresh", function() {
			var value = wn.model.get_value(me.doctype, me.docname, me.fieldname);
			me.$wrapper.html(value);
		})
	}
});

wn.ui.form.ControlInput = wn.ui.form.Control.extend({
	make: function() {
		// parent element
		this.$wrapper = $('<div class="control-group">\
			<label class="control-label"></label>\
			<div class="controls">\
				<div class="control-input"></div>\
				<div class="control-value like-disabled-input" style="display: none;"></div>\
			</div>\
		</div>').appendTo(this.parent);
		this.wrapper = this.$wrapper.get(0);
		this.wrapper.fieldobj = this; // reference for event handlers

		this.label_area = this.label_span = this.$wrapper.find(".control-label").get(0);
		this.input_area = this.$wrapper.find(".control-input").get(0);
		this.disp_area = this.$wrapper.find(".control-value").get(0);

		// set description
		this.set_max_width();
		this.setup_update_on_refresh();
	},
	set_max_width: function() {
		if(['Code', 'Text Editor', 'Text', 'Small Text', 'Table', 'HTML']
			.indexOf(this.df.fieldtype)==-1) {
			this.$wrapper.css({"max-width": "600px"});
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
				if(me.docname && me.set_input) {
					me.value = wn.model.get_value(me.doctype, me.docname, me.df.fieldname);

					if(me.disp_status=="Write") {
						$(me.disp_area).toggle(false);
						$(me.input_area).toggle(true);
						!me.has_input && me.make_input();
						me.set_input(me.value);
					} else {
						$(me.input_area).toggle(false);
						me.disp_area && $(me.disp_area)
							.toggle(true)
							.html(
								wn.format(me.value, me.df, null, locals[me.doctype][me.name])
							);
					}
				}

				me.set_description();
				me.set_label();
				me.set_mandatory();
			}
			
		})
	},
	set_label: function() {
		if(this.df.label==this._description) 
			return;
		this.label_span.innerHTML = wn._(this.df.label);
		this._label = this.df.label;
	},
	set_description: function() {
		if(this.df.description==this._description) return;
		if(this.df.description) {
			if(!this.$wrapper.find(".help-box").length) {
				$('<p class="help-box small text-muted"></p>').appendTo(this.input_area);
			}
			this.$wrapper.find(".help-box").html(this.df.description);
		} else {
			this.$wrapper.find(".help-box").empty().toggle(false);
		}
		this._description = this.df.description;
	},
	set_mandatory: function() {
		this.$wrapper.toggleClass("has-error", (this.df.reqd 
			&& (this.value==null || this.value=="")) ? true : false);
	},
	set_model_value: function(value) {
		wn.model.set_value(this.doctype, this.docname, this.df.fieldname, value);
		this.frm && this.frm.dirty();
	}
});

wn.ui.form.ControlData = wn.ui.form.ControlInput.extend({
	html_element: "input",
	input_type: "text",
	make_input: function() {
		this.$input = $("<"+ this.html_element +">")
			.attr("type", this.input_type)
			.attr("placeholder", this.df.placeholder || "")
			.attr("data-fieldtype", this.df.fieldtype)
			.addClass("col-span-12")
			.prependTo(this.input_area)
		this.input = this.$input.get(0);
		this.has_input = true;
		this.bind_change_event();
	},
	bind_change_event: function() {
		var me = this;
		this.$input.on("change", this.change || function() {
			if(me.doctype && me.docname && me.get_value) {
				var value = me.parse ? 
					me.parse(me.get_value()) :
					me.get_value();

				me.validate ?
				 	me.validate(value, function() { me.set_model_value(value); }) :
					me.set_model_value(value);
			}
		});
	},
	set_input: function(val) {
		this.$input.val(this.format_for_input(val));
	},
	get_value: function() {
		return this.$input.val();
	},
	format_for_input: function(val) {
		return val==null ? "" : val;
	},
	validate: function(v, callback) {
		if(this.df.options == 'Phone') {
			if(v+''=='')return '';
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
			if(v+''=='')return '';
			if(!validate_email(v)) {
				msgprint(wn._("Invalid Email") + ": " +  v);
					callback("");
			} else
				callback(v);
		} else {
			callback(v);
		}
	}
});

wn.ui.form.ControlPassword = wn.ui.form.ControlData.extend({
	input_type: "password"
});

wn.ui.form.ControlInt = wn.ui.form.ControlData.extend({
	make_input: function() {
		this._super();
		this.$input.css({"text-align": "right"})
	},
	validate: function(value, callback) {
		return callback(cint(value, null));
	}
});

wn.ui.form.ControlFloat = wn.ui.form.ControlInt.extend({
	validate: function(value, callback) {
		return callback(isNaN(parseFloat(value)) ? null : flt(value));
	},
	format_for_input: function(value) {
		value = format_number(parseFloat(value), 
			null, cint(wn.boot.sysdefaults.float_precision, null));
		return isNaN(value) ? "" : value;
	}
});

wn.ui.form.ControlCurrency = wn.ui.form.ControlFloat.extend({
	format_for_input: function(value) {
		value = format_number(parseFloat(value), 
			get_number_format(this.get_currency()));
		return isNaN(value) ? "" : value;
	},
	get_currency: function() {
		return wn.meta.get_field_currency(this.df, this.get_doc());
	}
});

wn.ui.form.ControlPercent = wn.ui.form.ControlFloat;

wn.ui.form.ControlDate = wn.ui.form.ControlData.extend({
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
			(wn.boot.sysdefaults.date_format || 'yy-mm-dd').replace('yyyy','yy')
		this.$input.datepicker(this.datepicker_options);
	},
	parse: function(value) {
		return dateutil.user_to_str(value);
	},
	format_for_input: function(value) {
		return dateutil.str_to_user(value);
	},
	validate: function(value, callback) {
		var value = wn.datetime.validate(value);
		if(!value) {
			msgprint (wn._("Date must be in format") + ": " + (sys_defaults.date_format || "yyyy-mm-dd"));
			callback("");
		}
		return callback(value);
	}
})

import_timepicker = function() {
	wn.require("lib/js/lib/jquery/jquery.ui.slider.min.js");
	wn.require("lib/js/lib/jquery/jquery.ui.sliderAccess.js");
	wn.require("lib/js/lib/jquery/jquery.ui.timepicker-addon.css");
	wn.require("lib/js/lib/jquery/jquery.ui.timepicker-addon.js");	
}

wn.ui.form.ControlTime = wn.ui.form.ControlData.extend({
	make_input: function() {
		import_timepicker();
		this._super();
		this.$input.timepicker({
			timeFormat: 'hh:mm:ss',
		});
	}
});

wn.ui.form.ControlDateTime = wn.ui.form.ControlDate.extend({
	set_datepicker: function() {
		this.datepicker_options.dateFormat = 
			(wn.boot.sysdefaults.date_format || 'yy-mm-dd').replace('yyyy','yy')
		this.datepicker_options.timeFormat = "hh:mm:ss";

		this.$input.datetimepicker(this.datepicker_options);
	},
	make_input: function() {
		import_timepicker();
		this._super();
	},
	
});

wn.ui.form.ControlText = wn.ui.form.ControlData.extend({
	html_element: "textarea"
});

wn.ui.form.ControlLongText = wn.ui.form.ControlText;
wn.ui.form.ControlSmallText = wn.ui.form.ControlText;

wn.ui.form.ControlCheck = wn.ui.form.ControlData.extend({
	input_type: "checkbox",
	parse: function(value) {
		return this.input.checked ? 1 : 0;
	},
	validate: function(value, callback) {
		return callback(cint(value));
	},
	set_input: function(value) {
		this.input.checked = value ? 1 : 0;
	}
});

wn.ui.form.ControlButton = wn.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this.$input = $('<button class="btn">')
			.prependTo(me.input_area)
			.on("click", function() {
				if(me.frm && me.frm.cscript) {
					if(me.frm.cscript[me.df.fieldname]) {
						me.frm.runclientscript(me.df.fieldname, me.doctype, me.docname);
					} else {
						me.frm.runscript(me.df.options, me);
					}
				} 
			});
		this.input = this.$input.get(0);
		this.has_input = true;
	},
	set_label: function() {
		this.$input && this.$input.html(this.df.label);
	}
});

wn.ui.form.ControlSelect = wn.ui.form.ControlData.extend({
	html_element: "select",
	make_input: function() {
		var me = this;
		this._super();
		if(this.df.options=="attach_files:") {
			this.setup_attachment();
		}
		this.set_options();
		this.$wrapper.on("refresh", function() {
			me.set_options();
			var value = wn.model.get_value(me.doctype, me.docname, me.fieldname);
			if(me.doctype && me.docname) {
				
				// model value is not an option,
				// set the default option (displayed)
				if(me.$input.val() != value) {
					me.set_model_value(me.$input.val());
				}
			}
		})
	},
	setup_attachment: function() {
		var me = this;
		$(this.input).css({"width": "70%"});
		$("<button class='btn' title='"+ wn._("Add attachment") + "'\
			style='margin-bottom: 9px; \
			padding-left: 6px; padding-right: 6px; margin-left: 6px;'>\
			<i class='icon-plus'></i></button>")
			.click(function() {
				me.frm.attachments.new_attachment();
			})
			.appendTo(this.input_area);
	},
	set_options: function() {
		var options = this.df.options || [];
		if(this.df.options=="attach_files:") {
			options = this.get_file_attachment_list();
		} else if(typeof this.df.options==="string") {
			options = this.df.options.split("\n");
		}
		
		if(this.in_filter && options[0] != "") {
			options = add_lists([''], options);
		}

		this.$input.empty().add_options(options || []);
	},
	get_file_attachment_list: function() {
		if(!this.frm) return;
		var fl = this.frm.doc.file_list;
		if(fl) {
			this.set_description("");
			var fl = JSON.parse(fl),
				options = [];
			for(var fname in fl) {
				if(fname.substr(0,4)!="http")
					fname = "files/" + fname;
				options.push(fname);
			}
			return options;
		} else {
			this.set_description(wn._("Please attach a file first."))
			return [""];
		}
	}
});