// ABOUT

var about_dialog;

function show_about() {
	if(!about_dialog) {
		var d = new Dialog(360,480, 'About')
	
		d.make_body([
			['HTML', 'info']
		]);
		
		d.rows['info'].innerHTML = "<div style='padding: 16px;'><center>"
			+"<h2>Powered by Web Notes Framework</h2>"
			+"<p style='color: #888'>Open Source Python + JS Framework</p>"
			+"<p>Code Repository: <a href='http://code.google.com/p/wnframework'>http://code.google.com/p/wnframework</a></p>"
			+"<p>Forum: <a href='http://groups.google.com/group/wnframework'>http://groups.google.com/group/wnframework</a></p>"
			+"<p>Website: <a href='http://wnframework.org'>http://wnframework.org/</a></p>"			
			+"</div>";
	
		about_dialog = d;
	}
	about_dialog.show();
}
