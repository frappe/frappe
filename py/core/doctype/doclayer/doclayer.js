cur_frm.cscript.doc_type = function(doc, dt, dn) {
	//console.log(doc);
	//console.log(doc_type);

	$c_obj(make_doclist(dt, dn), 'get', '', function(r, rt) {
		cur_frm.refresh();
		//console.log(arguments);
	});
}

cur_frm.cscript.refresh = function(doc, dt, dn) {
	cur_frm.frm_head.page_head.buttons.Save.hidden=1;
	cur_frm.page_layout.footer.hidden = 1;
	cur_frm.add_custom_button('Update', function() {
		if(cur_frm.fields_dict['doc_type'].value) {
			$c_obj(make_doclist(dt, dn), 'post', '', function(r, rt) {
				console.log(arguments);
			});	
		}
	},1);
}
