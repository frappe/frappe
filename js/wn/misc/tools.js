wn.markdown = function(txt) {
	if(!wn.md2html) {
		wn.require('js/lib/showdown.js');
		wn.md2html = new Showdown.converter();
	}
	return '<div class="markdown">' + wn.md2html.makeHtml(txt) + '</div>';
}