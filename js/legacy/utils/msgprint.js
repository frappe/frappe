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
	
	if(msg instanceof Array) {
		$.each(msg, function(i,v) {
			if(v)msgprint(v);
		})
		return;
	}
	
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
