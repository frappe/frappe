wn.make_editable = function(editor, doctype, name, fieldname) {
	wn.require("js/editor.min.js");
	bseditor = new bsEditor({
		editor: editor,
		onsave: function(bseditor) {
			wn.call({
				type: "POST",
				method: "webnotes.client.set_value",
				args: {
					doctype: doctype,
					name: name,
					fieldname: fieldname,
					value: editor.html()
				},
				callback: function(r) {
					wn.msgprint(r.exc ? "Error" : "Saved");
					if(!r.exc)
						editor.html(r.message[0][fieldname]);
				}
			});
		}
	});
}
