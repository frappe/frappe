// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Blog Post', {
	refresh: function(frm) {
		generate_google_search_preview(frm)
	},
	title: function(frm) {
		generate_google_search_preview(frm)
	},
	meta_description:function(frm){
		generate_google_search_preview(frm)
	},
	description:function(frm){
		generate_google_search_preview(frm)
	}
});
function generate_google_search_preview(frm){
	frm.call('get_url').then((r)=>{
		let seo_title = frm.doc.title
		seo_title = seo_title.slice(0,60)
		let seo_description =  frm.doc.meta_description || frm.doc.description
		seo_description = seo_description.slice(0,160)
		let google_preview = frm.get_field("google_preview")
		google_preview.html(`
			<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400&display=swap" rel="stylesheet">			
			<div style="max-width: 750px;">
			<div>
				<cite style="color: #006621;
					font-style: normal;
					font-size: 14px;
					display: inline-block;
					font-family: 'Open Sans'; font-size:14px;line-height:1.3; margin: 0 0">${ r.message + '/' + frm.doc.route }
				</cite>
				<div style="max:width: 580px">
					<h3 style="color:#1a0dab; font-family: 'Open Sans'; font-size:20px; line-height:1.3; hover:underline; margin: 0 0"><a style="color:#1a0dab;">
						${ seo_title }</a></h3>
				</div>
					<p style="color: #545454;
					font-size: small;
					line-height: 1.4;
					font-family: 'Open Sans'; font-size:14px; line-height:1.3; margin: 0 0">
					${ frm.doc.published_on }-${seo_description}
				</p>	
			</div>
			</div>	
		`)
	});	
}
