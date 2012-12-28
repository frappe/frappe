// for license information please see license.txt

wn.provide("wn.form.formatters")
wn.form.formatters = {
	Data: function(value) {
		return value==null ? "" : value
	},
	Float: function(value) {
		return "<div style='text-align: right'>" + flt(value, 6) + "</div>";
	},
	Int: function(value) {
		return cint(value);
	},
	Currency: function(value) {
		return "<div style='text-align: right'>" + fmt_money(value) + "</div>";
	},
	Check: function(value) {
		return value ? "<i class='icon-ok'></i>" : "<i class='icon'></i>";
	},
	Link: function(value, docfield) {
		if(!value) return "";
		if(docfield && docfield.options) {
			return repl('<a href="#Form/%(doctype)s/%(name)s">\
				<i class="icon icon-share" title="Open %(name)s" \
				style="margin-top:-1px"></i></a> %(name)s', {
				doctype: docfield.options,
				name: value
			});			
		} else {
			return value;
		}
	},
	Date: function(value) {
		return dateutil.str_to_user(value);
	},
	Text: function(value) {
		if(value) {
			var tags = ["<p[^>]>", "<div[^>]>", "<br[^>]>"];
			var match = false;

			for(var i=0; i<tags.length; i++) {
				if(value.match(tags[i])) {
					match = true;
				}
			}

			if(!match) {
				return replace_newlines(value);
			}
		}

		return wn.form.formatters.Data(value);
	},
	Tag: function(value) {
		var html = "";
		$.each((value || "").split(","), function(i, v) {
			if(v) html+= '<span class="label label-info" \
				style="margin-right: 7px; cursor: pointer;"\
				data-field="_user_tags" data-label="'+v+'">'+v +'</span>';
		});
		return html;
	},
	SmallText: function(value) {
		return wn.form.formatters.Text(value);
	},
	WorkflowState: function(value) {
		workflow_state = wn.model.get("Workflow State", value)[0];
		if(workflow_state) {
			return repl("<span class='label label-%(style)s' \
				data-workflow-state='%(value)s'\
				style='padding-bottom: 4px; cursor: pointer;'>\
				<i class='icon-small icon-white icon-%(icon)s'></i> %(value)s</span>", {
					value: value,
					style: workflow_state.style.toLowerCase(),
					icon: workflow_state.icon
				});
		} else {
			return "<span class='label'>" + value + "</span>";						
		}
	}
}

wn.form.get_formatter = function(fieldtype) {
	return wn.form.formatters[fieldtype.replace(/ /g, "")] || wn.form.formatters.Data;
}