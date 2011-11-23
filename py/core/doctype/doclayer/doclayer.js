cur_frm.cscript.doc_type = function(doc, dt, dn) {
	//console.log(doc);
	//console.log(doc_type);

	$c_obj(make_doclist(dt, dn), 'get', '', function(r, rt) {
		cur_frm.refresh();
		//console.log(arguments);
	});
}

cur_frm.cscript.onload = function(doc, dt, dn) {
	cur_frm.grids[0].grid.tbar_div.style.width = "30%";
	p = cur_frm.grids[0].grid.tbar_tab.children[0].children[0];
	p.removeChild(p.children[0])
	p.removeChild(p.children[0])
}

cur_frm.cscript.refresh = function(doc, dt, dn) {
	//console.log(p)
	cur_frm.frm_head.timestamp_area.hidden = true;
	cur_frm.frm_head.page_head.buttons.Save.hidden = true;
	cur_frm.page_layout.footer.hidden = true;
	cur_frm.tip_wrapper.id = 'tip_wrapper';
	if(doc.doc_type) { $('#tip_wrapper').slideUp('slow'); }

	
	cur_frm.add_custom_button('Update', function() {
		if(cur_frm.fields_dict['doc_type'].value) {
			$c_obj(make_doclist(dt, dn), 'post', '', function(r, rt) {
				if(r.exc) {
					msgprint(r.exc);
				} else {
					cur_frm.frm_head.status_area.innerHTML = 
					'<span style="padding: 2px; background-color: rgb(0, 170, 17); \
					color: rgb(255, 255, 255); font-weight: bold; margin-left: 0px; \
					font-size: 11px;">Saved</span>';
					//console.log(arguments);
				}
			});	
		}
	},1);
	cur_frm.frm_head.page_head.buttons.Update.className = "cupid-green";
	
	cur_frm.add_custom_button('Refresh Form', function() {
		cur_frm.cscript.doc_type(doc, dt, dn);
	}, 1);
	
	cur_frm.add_custom_button('Reset to defaults', function() {
		cur_frm.confirm('This will <b>remove the customizations</b> defined for this form.<br /><br />' 
		+ 'Are you sure you want to <i>reset to defaults</i>?', doc, dt, dn);
	}, 1);

	if(!doc.doc_type) {
		cur_frm.set_tip('You can start by selecting a Type from the drop down menu')
		$('#tip_wrapper').fadeIn();
		var page_head = cur_frm.frm_head.page_head;
		page_head.buttons['Update'].disabled = true;
		page_head.buttons['Refresh Form'].disabled = true;
		page_head.buttons['Reset to defaults'].disabled = true;
	}
}

cur_frm.confirm = function(msg, doc, dt, dn) {
	var d = new wn.widgets.Dialog({
		title: 'Reset To Defaults',
		width: 500
	});

	$y(d.body, {padding: '32px', textAlign: 'center'});

	$a(d.body, 'div', '', '', msg);

	var button_wrapper = $a(d.body, 'div');
	$y(button_wrapper, {paddingTop: '15px'});
	
	var proceed_btn = $btn(button_wrapper, 'Proceed', function() {
		$c_obj(make_doclist(dt, dn), 'delete', '', function(r, rt) {
			//console.log(arguments);
			if(r.exc) {
				msgprint(r.exc);
			} else {
				cur_frm.confirm.dialog.hide();
				cur_frm.refresh();
				cur_frm.frm_head.status_area.innerHTML = 
				'<span style="padding: 2px; background-color: rgb(0, 170, 17); \
				color: rgb(255, 255, 255); font-weight: bold; margin-left: 0px; \
				font-size: 11px;">Saved</span>';
			}
		});	
	});

	$y(proceed_btn, {marginRight: '20px', fontWeight: 'bold'});

	var cancel_btn = $btn(button_wrapper, 'Cancel', function() {
		cur_frm.confirm.dialog.hide();
	});

	cancel_btn.className = 'cupid-green';
	$y(cancel_btn, {fontWeight: 'bold'});

	cur_frm.confirm.dialog = d;
	d.show();
}
