frappe.make_editable = function(editor, doctype, name, fieldname) {
	frappe.require("/assets/js/editor.min.js");
	
	WebPageEditor = bsEditor.extend({
		onhide: function(action) {
			this._super(action);
			this.toggle_edit_mode(false);
		},
		setup_editor: function(editor) {
			this._super(editor);
			this.toggle_edit_mode(false);
		},
		toggle_edit_mode: function(bool) {
			var me = this;
			this._super(bool);
			
			if(!bool) {
				// remove existing web page editor toggles
				$('li.editable-toggle + li').remove();
				$('li.editable-toggle').remove();
				
				var $edit_btn = $(repl('<li class="editable-toggle">\
					<a href="#"><i class="icon-fixed-width icon-pencil"></i>Edit %(doctype)s</a></li>\
					<li class="divider"></li>', {doctype: doctype}))
					.prependTo($("#website-post-login ul.dropdown-menu"));
			
				$edit_btn.find("a")
					.on("click", function() {
						me.toggle_edit_mode(true);
						$edit_btn.remove();
						return false;
					});
			}
		}
	});
	
	bseditor = new WebPageEditor({
		editor: editor,
		onsave: function(bseditor) {
			frappe.call({
				type: "POST",
				method: "frappe.client.set_value",
				args: {
					doctype: doctype,
					name: name,
					fieldname: fieldname,
					value: bseditor.get_value()
				},
				callback: function(r) {
					frappe.msgprint(r.exc ? __("Error") : __("Saved"));
					if(!r.exc)
						editor.html(r.message[0][fieldname]);
				}
			});
		}
	});
};
