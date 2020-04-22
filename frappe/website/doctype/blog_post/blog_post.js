// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Blog Post', {
	refresh: function(frm) {
		frm.call('get_url').then((r)=>{
			let google_preview = frm.get_field("google_preview")
			google_preview.html(`
				<link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" rel="stylesheet">
				<link href="https://fonts.googleapis.com/css2?family=Open+Sans&family=Roboto&display=swap" rel="stylesheet">
				<cite style="color: #006621;
				font-style: normal;
				font-size: 14px;
				display: inline-block;
				font-family: 'Roboto, sans-serf'; font-size:14px;line-height:1.3; margin: 0 0">${ r.message + '/' + frm.doc.route } </cite>
				<h3 style="color:#1a0dab; font-family: 'Roboto', sans-serif; font-size:20px; line-height:1.3; hover:underline; margin: 0 0"><a style="color:#1a0dab;">
				${ frm.doc.title }</a></h3>
				<span style="color:808080; font-family: 'Roboto, sans-serf'; font-size:14px;line-height:1.3; margin: 0 0""">${ frm.doc.published_on } </span><span style="color: #545454;
				font-size: small;
				line-height: 1.4;
				word-wrap: break-word;
				font-family: 'Roboto, sans-serf'; font-size:14px;line-height:1.3; margin: 0 0"">${frm.doc.meta_description}
			`)
		})
	}
});
