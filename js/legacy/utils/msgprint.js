var msg_dialog;
function msgprint(msg, issmall, callback) {
	if(!msg) return;
	
	if(typeof(msg)!='string')
		msg = JSON.stringify(msg);

	if(issmall) { show_alert(msg); return; }

	// small message
	if(msg.substr(0,8)=='__small:') {
		show_alert(msg.substr(8));
		return;
	}

	if(!msg_dialog) {
		msg_dialog = new Dialog(500, 200, "Message");
		msg_dialog.make_body([['HTML','Msg']])
		msg_dialog.onhide = function() {
			msg_dialog.msg_area.innerHTML = '';
			$dh(msg_dialog.msg_icon);
			if(msg_dialog.custom_onhide) msg_dialog.custom_onhide();
		}
		$y(msg_dialog.rows['Msg'], {fontSize:'14px', lineHeight:'1.5em', padding:'16px'})
		var t = make_table(msg_dialog.rows['Msg'], 1, 2, '100%',['20px','250px'],{padding:'2px',verticalAlign: 'Top'});
		msg_dialog.msg_area = $td(t,0,1);
		msg_dialog.msg_icon = $a($td(t,0,0),'img');
	}

	// blur bg
	if(!msg_dialog.display) msg_dialog.show();

	// set message content
	var has_msg = msg_dialog.msg_area.innerHTML ? 1 : 0;

	var m = $a(msg_dialog.msg_area,'div','');
	if(has_msg)$y(m,{marginTop:'4px'});

	$dh(msg_dialog.msg_icon);
	if(msg.substr(0,6).toLowerCase()=='error:') {
		msg_dialog.msg_icon.src = 'lib/images/icons/error.gif'; $di(msg_dialog.msg_icon); msg = msg.substr(6);
	} else if(msg.substr(0,8).toLowerCase()=='message:') {
		msg_dialog.msg_icon.src = 'lib/images/icons/application.gif'; $di(msg_dialog.msg_icon); msg = msg.substr(8);
	} else if(msg.substr(0,3).toLowerCase()=='ok:') {
		msg_dialog.msg_icon.src = 'lib/images/icons/accept.gif'; $di(msg_dialog.msg_icon); msg = msg.substr(3);
	}


	m.innerHTML = replace_newlines(msg);

	if(m.offsetHeight > 200) {
		$y(m, {height:'200px', width:'400px', overflow:'auto'})
	}
	
	msg_dialog.custom_onhide = callback;
	
}


// Floating Message
var growl_area;
function show_alert(txt) {
	if(!growl_area) {
		growl_area = $a(popup_cont, 'div', '', {position:'fixed', bottom:'8px', right:'8px', width: '320px', zIndex:10});
	}
	var wrapper = $a(growl_area, 'div', '', {position:'relative'});
	var body = $a(wrapper, 'div', 'notice');
	
	// close
	var c = $a(body, 'div', 'wn-icon ic-round_delete', {cssFloat:'right'});
	$(c).click(function() { $dh(this.wrapper) });
	c.wrapper = wrapper;
	
	// text
	var t = $a(body, 'div', '', { color:'#FFF' });
	$(t).html(txt);
	$(wrapper).hide().fadeIn(1000);
}