frappe.provide('frappe.communication_reconciliation')
frappe.communication_reconciliation.showhidden = function(){
	$(".hide-control").removeClass("hide-control")
}
frappe.ui.form.on("Communication Reconciliation", {
	onload: function(frm){
		var method = "frappe.desk.doctype.communication_reconciliation.communication_reconciliation.get_communication_doctype";
		cur_frm.get_field("reference_doctype").get_query = method;
		cur_frm.fields_dict["communication_list"].grid.get_field("reference_doctype").get_query = method;
	},
    	refresh: function(frm) {
		setTimeout(frappe.communication_reconciliation.showhidden, 1)
		frm.disable_save();
	},
	fetch: function(frm) {
		frappe.call({
			method: 'fetch',
			doc: frm.doc,
			callback: function (frm) {
				cur_frm.doc = frm.docs[0]
				origional = []
				var list = frm.docs[0].communication_list
				for ( i = 0; i < list.length; i++){
					origional.push({})
					origional[i].name = list[i].name
					origional[i].reference_doctype = list[i].reference_doctype
					origional[i].reference_name = list[i].reference_name
				}
				cur_frm.refresh()
				changed = {}
				$(".data-row").css("font-weight", "normal")
			}
		})
	},
	relink_bulk: function(frm) {
		frappe.call({
			method: 'relink_bulk',
			doc: frm.doc,
			args:{
				"changed_list": changed
			},
			callback: function (frm) {
				cur_frm.doc = frm.docs[0]
				origional = []
				var list = frm.docs[0].communication_list
				for ( i = 0; i < list.length; i++){
					origional.push({})
					origional[i].name = list[i].name
					origional[i].reference_doctype = list[i].reference_doctype
					origional[i].reference_name = list[i].reference_name
				}
				cur_frm.refresh()
				changed = {}
				$(".data-row").css("font-weight", "normal")
			}
		})
	}
});

frappe.ui.form.on("Communication Reconciliation item", {
	reference_doctype: function(frm){
		if (origional[cur_frm.cur_grid.doc.idx-1].reference_doctype!=cur_frm.cur_grid.doc.reference_doctype || last_reference_doctype != cur_frm.cur_grid.doc.reference_doctype) {
			cur_frm.cur_grid.doc.reference_name = ""
			last_reference_doctype = cur_frm.cur_grid.doc.reference_doctype
			cur_frm.cur_grid.refresh()
		}else{
			if (origional[cur_frm.cur_grid.doc.idx-1].reference_name===cur_frm.cur_grid.doc.reference_name) {
				cur_frm.cur_grid.row.css("font-weight", "normal")
			}
		}
	},
	reference_name: function(frm){
		if (origional[cur_frm.cur_grid.doc.idx-1].reference_name!=cur_frm.cur_grid.doc.reference_name) {
			cur_frm.cur_grid.row.css("font-weight", "Bold")
			var grid =cur_frm.cur_grid.doc
			changed[grid.name]= {"name":grid.name,"reference_doctype":grid.reference_doctype,"reference_name":grid.reference_name}
		}else {
			cur_frm.cur_grid.row.css("font-weight", "normal")
			delete changed[cur_frm.cur_grid.doc.name]
		}
	}
})
