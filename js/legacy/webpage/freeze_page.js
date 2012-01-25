var fcount = 0;
var frozen = 0;
var dialog_message;
var dialog_back;

function freeze(msg, do_freeze) {
	// blur
	if(!dialog_back) {
		dialog_back = $a($i('body_div'), 'div', 'dialog_back');
		if(isIE) dialog_back.style['filter'] = 'alpha(opacity=60)';
	}
	$ds(dialog_back);

	fcount++;
	frozen = 1;
}
function unfreeze() {
	if(dialog_message)
		$dh(dialog_message);
	if(!fcount)return; // anything open?
	fcount--;
	if(!fcount) {
		$dh(dialog_back);
		frozen = 0;
	}
}
