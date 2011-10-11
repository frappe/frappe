cur_frm.cscript.validate = function(doc, dt, dn) {
	return 1;
}

cur_frm.cscript['Set From Image'] = function(doc, dt, dn) {
	if(!doc.file_list) {
		msgprint('Please attach an image file first');
		return;
	}
	if(doc.content) {
		if(!confirm('Are you sure you want to overwrite the existing HTML?'))
			return;
	}

	var file_name = doc.file_list.split(',')[0]

	if(!in_list(['gif','jpg','jpeg','png'], file_name.split('.')[1].toLowerCase())) {
		msgprint("Please upload a web friendly (GIF, JPG or PNG) image file for the letter head");
		return;
	}

	img_link = '<div><img src="'+ wn.urllib.get_file_url(file_name) + '"/></div>'
	
	doc.content = img_link;
	refresh_field('content');
}