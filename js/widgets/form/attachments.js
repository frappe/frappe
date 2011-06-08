
// ATTACHMENT - Deprecated!!!

// ======================================================================================

_f.Frm.prototype.setup_attach = function() {
	var me = this;
	
	this.attach_area = $a(this.layout ? this.layout.cur_row.wrapper : this.body, 'div', 'attach_area');
	$(this.attach_area)
		.css('-moz-border-radius','5px')
		.css('-webkit-border-radius','5px');

	if(!this.meta.max_attachments)
		this.meta.max_attachments = 10;
	
	var tab = $a($a(this.attach_area, 'div'), 'table');
	tab.insertRow(0);
	var label_area = tab.rows[0].insertCell(0);
	var main_area = tab.rows[0].insertCell(1);

	this.files_area = $a(main_area, 'div');	
	this.btn_area = $a(main_area, 'div');

	$w(label_area, "33%");
	var d = $a(label_area, 'div');
	//var img = $a(d, 'img', '', {marginRight:'8px'}); img.src = 'images/icons/paperclip.gif';
	$a(d, 'span').innerHTML = '<h4>File Attachments:</h4>';
	
	// button
	var btn_add_attach = $btn(this.btn_area, '+ Add');
	
	btn_add_attach.onclick = function() {
		me.add_attachment();
		me.sync_attachments(me.docname);
		me.refresh_attachments();
	}
}

_f.Frm.prototype.refresh_attachments = function() {

	// render attachments
	var nattach = 0;
	for(var dn in this.attachments) {
		for(var i in this.attachments[dn]){
			var a = this.attachments[dn][i];
			if(a.docname!=this.docname)
				a.hide();
			else {
				a.show();
				nattach++;
				
				// show / hide delete button
				if(this.perm[0][WRITE] && this.editable && this.doc.docstatus < 1) { $ds(a.delbtn); }
				else { $dh(a.delbtn); }
			}
		}
	}
	
	// show / hide "Add" button
	if(this.perm[0][WRITE] && cint(this.doc.docstatus)==0) { 
		if(nattach >= cint(this.meta.max_attachments))
			$dh(this.btn_area);
		else
			$ds(this.btn_area);
	} else { 
		$dh(this.btn_area); 
	}	
}

_f.Frm.prototype.set_attachments = function() {
	//if(this.meta.issingle) /// why??
	//	return;

	this.attachments[this.docname] = [];	
	var atl = locals[this.doctype][this.docname].file_list;

	if(atl) {
		atl = atl.split('\n');

		// add new document attachments
		for(var i in atl) {
			var a = atl[i].split(',');
			var ff = this.add_attachment(a[0], a[1]);
		}
	}
}

_f.Frm.prototype.add_attachment = function(filename, fileid) {
	var at_id = this.attachments[this.docname].length;

	var ff = new _f.FileField(this.files_area, at_id, this);

	// set name and id if given
	if(filename)ff.filename = filename;
	if(fileid)ff.fileid = fileid;
	ff.docname = this.docname;
	
	this.attachments[this.docname][at_id] = ff;
	
	ff.refresh();
	return ff;
}

_f.Frm.prototype.sync_attachments = function(docname) {
	var fl = [];
	for(var i in this.attachments[docname]) {
		var a = this.attachments[docname][i];
		fl[fl.length] = a.filename + ',' + a.fileid;
	} 
	locals[this.doctype][docname].file_list = fl.join('\n')
}

// Handling File field

_f.FileField = function(parent, at_id, frm, addlink) {
	var me = this;
	this.at_id = at_id
	
	this.wrapper = $a(parent, 'div');
	var tab = $a(this.wrapper, 'table');

	tab.insertRow(0);
	var main_area = tab.rows[0].insertCell(0);
	var del_area = tab.rows[0].insertCell(1);
	
	// del button
	
	$w(del_area, '20%');
	this.delbtn = $a(del_area, 'div', 'link_type');
	this.delbtn.innerHTML = 'Remove';

	this.remove = function() {
		var yn = confirm("The document will be saved after the attachment is deleted for the changes to be permanent. Proceed?")
		if(yn) {
			var callback = function(r, rt) {
				me.wrapper.style.display = 'none';
				delete frm.attachments[frm.docname][me.at_id];
				frm.sync_attachments(frm.docname);
				var ret = frm.save('Save');
				if(ret=='Error')
					msgprint("error:The document was not saved. To make the removal permanent, you must save the document before closing.");
			}
				
			var fid = frm.attachments[frm.docname][me.at_id].fileid;
			if(fid) {
				$c('webnotes.widgets.form.remove_attach', args = {'fid': fid}, callback );
			}
	
		}
	}
	
	this.hide = function() { $dh(me.wrapper); }
	this.show = function() { $ds(me.wrapper); }

	this.delbtn.onclick = this.remove;
		
	// upload
	this.upload_div = $a(main_area, 'div');
	this.download_div = $a(main_area, 'div');

	this.uploader = new Uploader(this.upload_div,{from_form:1, doctype:frm.doctype, docname:frm.docname, at_id:at_id},_f.file_upload_done);
	
	// download
	this.download_link = $a(this.download_div, 'a', 'link_type');
	
	// fresh
	this.refresh = function() {
		if (this.filename) {
			$dh(this.upload_div);
			this.download_link.innerHTML = this.filename;
			this.download_link.href = outUrl + '?cmd=get_file&fname='+this.fileid;

			this.download_link.target = "_blank";
			$ds(this.download_div);
		} else {
			$ds(this.upload_div);
			$dh(this.download_div);
		}
	}
}

_f.file_upload_done = function(doctype, docname, fileid, filename, at_id) {
	
	var at_id = cint(at_id);
	
	// update file_list
	var frm = frms[doctype];
	var a = frm.attachments[docname][at_id];
	a.filename = filename;
	a.fileid = fileid;

	frm.sync_attachments(docname);
	
	a.refresh();
	var do_save = confirm('File Uploaded Sucessfully. You must save this document for the uploaded file to be registred. Save this document now?');
	if(do_save) {
		var ret = frm.save('Save');
		if(ret=='Error')msgprint("error:The document was not saved. To make the attachment permanent, you must save the document before closing.");
	} else {
		msgprint("error:The document was not saved. To make the attachment permanent, you must save the document before closing.");
	}
}
