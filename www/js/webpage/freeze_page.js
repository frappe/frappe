var fcount = 0;
var frozen = 0;
var dialog_message;
var dialog_back;

function freeze(msg, do_freeze) {
	// show message
	if(msg) {
		if(!dialog_message) {
			dialog_message = $a('dialogs','div','dialog_message');
			//$(dialog_message).corners();
		}

		var d = get_screen_dims();
		$y(dialog_message, {left : ((d.w - 250)/2) + 'px', top  : (get_scroll_top() + 200) + 'px'});
		dialog_message.innerHTML = '<div style="font-size:16px; color: #444; font-weight: bold; text-align: center;">'+msg+'</div>';
		$ds(dialog_message);
	} 
	
	// blur
	if(!dialog_back) {
		dialog_back = $a($i('body_div'), 'div', 'dialog_back');
		if(isIE) dialog_back.style['filter'] = 'alpha(opacity=60)';
	}

	$ds(dialog_back);
	$y(dialog_back, {height: get_page_size()[1] + 'px'});

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
		show_selects();
		frozen = 0;
	}
}

// Selects for IE6
// ------------------------------------

function hide_selects() { }

function show_selects() { }


//var fmessage;
