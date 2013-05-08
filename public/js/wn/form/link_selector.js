wn.ui.form.LinkSelector = Class.extend({
	_help: "Dialog box to select a Link Value",
	init: function(opts) {
		/* help: Options: doctype, get_query, target */
		$.extend(this, opts);
		
		var me = this;
		if(this.doctype!="[Select]") {
			wn.model.with_doctype(this.doctype, function(r) {
				me.make();
			});
		} else {
			this.make();
		}
	},
	make: function() {
		this.dialog = new wn.ui.Dialog({
			"title": "Select " + this.doctype,
			"fields": [
				{
					fieldtype: "Data", fieldname: "txt", label: "Beginning with",
					description: "You can use wildcard %" 
				},
				{
					fieldtype: "Select", fieldname: "search_field", label: "Search With"
				},
				{
					fieldtype: "Button", fieldname: "search", label: "Search",
				},
				{
					fieldtype: "HTML", fieldname: "results"
				}
			]
		});
		var search_fields = wn.model.get_value("DocType", this.doctype, "search_fields");
		if(this.doctype!="[Select]" && search_fields) {
			this.dialog.fields_dict.search_field.$input.add_options(search_fields.split(","));
		} else {
			this.dialog.fields_dict.search_field.$wrapper.toggle(false);
		}
		this.dialog.fields_dict.search.$input.on("click", function() {
			
		})
		this.dialog.show();
	}
})