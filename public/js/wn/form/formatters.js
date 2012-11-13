// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

wn.provide("wn.form.formatters")
wn.form.formatters = {
	Data: function(value) {
		return value==null ? "" : value
	},
	Float: function(value) {
		return (flt(value) || 0.0).toFixed(6);
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
		if(docfield.options) {
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
		if(value && value.indexOf("<br>")==-1 && value.indexOf("<p>")==-1 && value.indexOf("<div")==-1)
			return replace_newlines(value);

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
	WorkflowState: function(value) {
		workflow_state = wn.meta.get("Workflow State", value)[0];
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
	return wn.form.formatters[fieldtype] || wn.form.formatters.Data;
}