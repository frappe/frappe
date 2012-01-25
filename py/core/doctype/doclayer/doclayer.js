cur_frm.cscript.doc_type = function(doc, dt, dn) {
	$c_obj(make_doclist(dt, dn), 'get', '', function(r, rt) {
		cur_frm.refresh();
	});
}

cur_frm.cscript.onload = function(doc, dt, dn) {
	cur_frm.grids[0].grid.tbar_div.style.width = "30%";
	cur_frm.tip_wrapper.id = 'tip_wrapper';
	cur_frm.add_fields_help();
	cur_frm.load_doclabel_options(doc, dt, dn);
}

cur_frm.cscript.refresh = function(doc, dt, dn) {
	//console.log(p)
	cur_frm.frm_head.timestamp_area.hidden = true;
	cur_frm.frm_head.page_head.buttons.Save.hidden = true;
	cur_frm.page_layout.footer.hidden = true;
	if(doc.doc_type) { $('#tip_wrapper').slideUp('slow'); }

	//cur_frm.grids[0].grid.tab.rows[cur_frm.grids[0].grid.tab.rows.length-1].hidden = true;
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
		cur_frm.set_tip('You can start by selecting a Form Type from the drop down menu')
		$('#tip_wrapper').fadeIn();
		var page_head = cur_frm.frm_head.page_head;
		page_head.buttons['Update'].disabled = true;
		page_head.buttons['Refresh Form'].disabled = true;
		page_head.buttons['Reset to defaults'].disabled = true;
	}

	cur_frm.refresh_doctype_select(doc, dt, dn);
}

cur_frm.load_doclabel_options = function(doc, dt, dn) {
	$c_obj('DocLayer','get_doctype_list','', function(r,rt) {
		cur_frm.doctype_list = add_lists([""], r.message.doctype_list).join("\n");
		doc = locals[doc.doctype][doc.name]
		cur_frm.refresh_doctype_select(doc, dt, dn);
	});
}

cur_frm.refresh_doctype_select = function(doc, dt, dn) {
	var doc_type = cur_frm.fields_dict['doc_type'];
	doc_type.refresh_options(cur_frm.doctype_list);
	if(doc.doc_type) {
		doc_type.set_input(doc.doc_type);
	} else {
		doc_type.set_input('');
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


cur_frm.add_fields_help = function() {
	$(cur_frm.grids[0].parent).before(
		'<div style="padding: 10px">\
			<a id="fields_help" class="link_type">Help</a>\
		</div>');
	$('#fields_help').click(function() {
		var d = new wn.widgets.Dialog({
			title: 'Help: Field Properties',
			width: 600
		});

		var help =
			"<table cellspacing='25'>\
				<tr>\
					<td><b>Label</b></td>\
					<td>Set the display label for the field</td>\
				</tr>\
				<tr>\
					<td width='25%'><b>Options</b></td>\
					<td width='75%'>Specify the value of the field</td>\
				</tr>\
				<tr>\
					<td><b>Perm Level</b></td>\
					<td>\
						Assign a permission level to the field.<br />\
						(Permissions can be managed via Setup &gt; Permission Manager)\
					</td>\
				</tr>\
				<tr>\
					<td><b>Width</b></td>\
					<td>\
						Width of the input box<br />\
						Example: <i>120px</i>\
					</td>\
				</tr>\
				<tr>\
					<td><b>Reqd</b></td>\
					<td>Mark the field as Mandatory</td>\
				</tr>\
				<tr>\
					<td><b>In Filter</b></td>\
					<td>Use the field to filter records</td>\
				</tr>\
				<tr>\
					<td><b>Hidden</b></td>\
					<td>Hide field in form</td>\
				</tr>\
				<tr>\
					<td><b>Print Hide</b></td>\
					<td>Hide field in Standard Print Format</td>\
				</tr>\
				<tr>\
					<td><b>Report Hide</b></td>\
					<td>Hide field in Report Builder</td>\
				</tr>\
				<tr>\
					<td><b>Allow on Submit</b></td>\
					<td>Allow field to remain editable even after submission</td>\
				</tr>\
				<tr>\
					<td><b>Depends On</b></td>\
					<td>\
						Show field if a condition is met<br />\
						Example: <code>eval:doc.status=='Cancelled'</code>\
						 on a field like \"reason_for_cancellation\" will reveal \
						\"Reason for Cancellation\" only if the record is Cancelled.\
					</td>\
				</tr>\
				<tr>\
					<td><b>Description</b></td>\
					<td>Show a description below the field</td>\
				</tr>\
				<tr>\
					<td><b>Default</b></td>\
					<td>Specify a default value</td>\
				</tr>\
				<tr>\
					<td></td>\
					<td><a class='link_type' \
							onclick='cur_frm.fields_help_dialog.hide()'\
							style='color:grey'>Press Esc to close</a>\
					</td>\
				</tr>\
			</table>"
		
		$y(d.body, {padding: '32px', textAlign: 'center', lineHeight: '200%'});

		$a(d.body, 'div', '', {textAlign: 'left'}, help);

		d.show();

		cur_frm.fields_help_dialog = d;

	});
}
