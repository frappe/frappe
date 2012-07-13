// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

var msg_dialog;

function msgprint(msg, title) {
	if(!msg) return;
	
	if(typeof(msg)!='string')
		msg = JSON.stringify(msg);

	// small message
	if(msg.substr(0,8)=='__small:') {
		show_alert(msg.substr(8)); return;
	}

	if(!msg_dialog) {
		msg_dialog = new wn.ui.Dialog({
			title:"Message",
			onhide: function() {
				msg_dialog.msg_area.empty();
			}
		});
		msg_dialog.msg_area = $('<div class="msgprint">')
			.appendTo(msg_dialog.body);
	}

	if(msg.search(/<br>|<p>|<li>/)==-1)
		msg = replace_newlines(msg);

	msg_dialog.set_title(title || 'Message')
	msg_dialog.msg_area.append(msg);
	msg_dialog.show();
	
}

/*
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
		msg_dialog.msg_icon.src = 'images/lib/icons/error.gif'; $di(msg_dialog.msg_icon); msg = msg.substr(6);
	} else if(msg.substr(0,8).toLowerCase()=='message:') {
		msg_dialog.msg_icon.src = 'images/lib/icons/application.gif'; $di(msg_dialog.msg_icon); msg = msg.substr(8);
	} else if(msg.substr(0,3).toLowerCase()=='ok:') {
		msg_dialog.msg_icon.src = 'images/lib/icons/accept.gif'; $di(msg_dialog.msg_icon); msg = msg.substr(3);
	}

	if(msg.search(/<br>|<p>/)==-1)
		m.innerHTML = replace_newlines(msg);

	if(m.offsetHeight > 200) {
		$y(m, {height:'200px', width:'400px', overflow:'auto'})
	}
	
	msg_dialog.custom_onhide = callback;
	
}*/


// Floating Message
var growl_area;
function show_alert(txt, id) {
	if(!growl_area) {
		if(!$('#dialog-container').length) {
			$('<div id="dialog-container">').appendTo('body');
		}
		growl_area = $a($i('dialog-container'), 'div', '', {position:'fixed', bottom:'8px', right:'8px', width: '320px', zIndex:10});
	}
	var wrapper = $a(growl_area, 'div', '', {position:'relative'});
	var body = $a(wrapper, 'div', 'notice');
	
	// close
	var c = $a(body, 'i', 'icon-remove-sign', {cssFloat:'right', cursor: 'pointer'});
	$(c).click(function() { $dh(this.wrapper) });
	c.wrapper = wrapper;
	
	// text
	var t = $a(body, 'div', '', { color:'#FFF' });
	$(t).html(txt);
	if(id) { $(t).attr('id', id); }
	$(wrapper).hide().fadeIn(1000);
}
