// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Blog Post', {
	refresh: function(frm) {
		generate_google_search_preview(frm);
	},
	title: function(frm) {
		generate_google_search_preview(frm);
	},
	meta_description: function(frm) {
		generate_google_search_preview(frm);
	},
	blog_intro: function(frm) {
		generate_google_search_preview(frm);
	}
});
function generate_google_search_preview(frm){
	frm.call('get_url').then((r)=>{
		let google_preview = frm.get_field("google_preview");
		let seo_title = (frm.doc.title).slice(0, 60);
		let seo_description =  (frm.doc.meta_description || frm.doc.blog_intro || "").slice(0, 160);

		google_preview.html(`
			<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400&display=swap" rel="stylesheet">

			<div class="frappe-control">
				<div class="form-group">
					<div class="clearfix">
						<label class="control-label" style="padding-right: 0px;">Google Search Listing Preview</label>
					</div>
					<div class="control-input-wrapper">
						<div class="control-input">
							<div>
							<cite style="color: #006621; font-style: normal; font-size: 14px; display: inline-block;
								font-family: 'Open Sans'; font-size: 14px; line-height: 1.3; margin: 0 0">
								${ r.message + '/' + frm.doc.route }
							</cite>
							<h3 style="color: #1a0dab; font-family: 'Open Sans'; font-size: 20px; line-height: 1.3; hover: underline; margin: 0 0">
								<a style="color:#1a0dab;">
									${ seo_title }
								</a>
							</h3>
							<p style="color: #545454; font-size: small; line-height: 1.4; font-family: 'Open Sans'; font-size:14px;
								line-height:1.3; margin: 0 0">
								${ frm.doc.published_on } - ${ seo_description }
							</p>
							</div>
						</div>
						<br>
						<p class="help-box small text-muted hidden-xs">
							Google currently displays 155-160 characters of the meta description in the search result. You can also check the previews for <a href="https://developers.facebook.com/tools/debug/" target="_blank">Facebook</a> and <a href="https://cards-dev.twitter.com/validator" target="_blank">Twitter</a> using their debugger tools. 
						</p>
					</div>
				</div>
			</div>
		`)
	});
}
