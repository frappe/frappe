wn.widgets.form.sidebar.Attachments = function(parent, sidebar, doctype, docname) {
	var me = this;
	this.frm = sidebar.form;
	
	this.make = function() {
		if(this.wrapper) this.wrapper.innerHTML = '';
		else this.wrapper = $a(parent, 'div', 'sidebar-comment-wrapper');
		
		// attachment
		this.attach_wrapper = $a(this.wrapper, 'div');
		
		// no attachments if file is unsaved
		if(this.frm.doc.__islocal) {
			this.attach_wrapper.innerHTML = 'Attachments can be uploaded after saving'
			return;
		}
		
		// no of attachments
		var n = this.frm.doc.file_list ? this.frm.doc.file_list.split('\n').length : 0;
		
		// button if the number of attachments is less than max
		if(n < this.frm.meta.max_attachments || !this.frm.meta.max_attachments) {
			this.btn = $btn($a(this.wrapper, 'div', 'sidebar-comment-message'), 'Add', 
				function() { me.add_attachment() });			
		}
		
		// render
		this.render();

	}

	// create Attachment objects from
	// the file_list
	this.render = function() {
		// clear exisitng
		this.attach_wrapper.innerHTML = ''

		var doc = locals[me.frm.doctype][me.frm.docname];
		var fl = doc.file_list ? doc.file_list.split('\n') : [];
		
		// add attachment objects
		for(var i=0; i<fl.length; i++) {
			new wn.widgets.form.sidebar.Attachment(this.attach_wrapper, fl[i], me.frm)
		}
	}

	// call the Uploader object to save an attachment
	// using the file mamanger
	this.add_attachment = function() {
		if(!this.dialog) {
			this.dialog = new wn.widgets.Dialog({
				title:'Add Attachment',
				width: 400
			})
			$y(this.dialog.body, {margin:'13px'})
			this.dialog.make();
		}
		this.dialog.body.innerHTML = '';
		this.dialog.show();
		
		this.uploader = new Uploader(this.dialog.body, {
			from_form: 1,
			doctype: doctype,
			docname: docname,
			at_id: this.at_id
		}, wn.widgets.form.file_upload_done);		
	}
	
	this.make();
}

wn.widgets.form.sidebar.Attachment = function(parent, filedet, frm) {
	filedet = filedet.split(',')
	this.filename = filedet[0];
	this.fileid = filedet[1];
	this.frm = frm;
	var me = this;
	
	this.wrapper = $a(parent, 'div', 'sidebar-comment-message');

	// remove from the file_list property of the doc
	this.remove_fileid = function() {
		var doc = locals[me.frm.doctype][me.frm.docname];
		var fl = doc.file_list.split('\n'); new_fl = [];
		for(var i=0; i<fl.length; i++) {
			if(fl[i].split(',')[1]!=me.fileid) new_fl.push(fl[i]);
		}
		doc.file_list = new_fl.join('\n');
	}
		
	// download
	this.ln = $a(this.wrapper, 'a', 'link_type', {fontSize:'11px'}, this.filename);
	this.ln.href = outUrl + '?cmd=get_file&fname='+this.fileid;
	this.ln.target = '_blank';
	
	// remove
	this.del = $a(this.wrapper, 'span', 'close', '', '&#215;');
	this.del.onclick = function() {
		var yn = confirm("Are you sure you want to delete the attachment?")
		if(yn) {
			var callback = function(r, rt) {
				// update timestamp
				locals[me.frm.doctype][me.frm.docname].modified = r.message;
				$dh(me.wrapper);
				me.remove_fileid();
				frm.refresh();
			}				
			$c('webnotes.widgets.form.utils.remove_attach', 
				args = {'fid': me.fileid, dt: me.frm.doctype, dn: me.frm.docname }, callback );
		}		
	}
}

// this function will be called after the upload is done
// from webnotes.utils.file_manager
wn.widgets.form.file_upload_done = function(doctype, docname, fileid, filename, at_id, new_timestamp) {
	
	var at_id = cint(at_id);
	
	// add to file_list
	var doc = locals[doctype][docname];
	if(doc.file_list) {
		var fl = doc.file_list.split('\n')
		fl.push(filename + ',' + fileid)
		doc.file_list = fl.join('\n');
	}
	else
		doc.file_list = filename + ',' + fileid;
	
	// update timestamp
	doc.modified = new_timestamp;
	
	// update file_list
	var frm = frms[doctype];
	frm.attachments.dialog.hide();
	msgprint('File Uploaded Sucessfully.');
	frm.refresh();
}
