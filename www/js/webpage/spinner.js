var _loading_div;
function set_loading() {
	if(page_body.wntoolbar)$ds(page_body.wntoolbar.spinner);
	$y(document.getElementsByTagName('body')[0], {cursor:'progress'});
	if(page_body.on_start_spinner) page_body.on_start_spinner();
	pending_req++;
}

function hide_loading() {
	pending_req--;
	if(!pending_req){
		$y(document.getElementsByTagName('body')[0], {cursor:'default'});
		if(page_body.wntoolbar)
			var d = page_body.wntoolbar.spinner;
		if(d) $dh(d);
		if(page_body.on_stop_spinner) page_body.on_stop_spinner();
	}
}