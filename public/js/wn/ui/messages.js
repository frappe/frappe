wn.provide("wn.messages")

wn.messages.waiting = function(parent, msg, bar_percent) {
	if(!bar_percent) bar_percent = '100';
	return $(repl('<div class="well" style="width: 63%; margin: 30px auto;">\
		<p style="text-align: center;">%(msg)s</p>\
		<div class="progress progress-striped active">\
			<div class="bar" style="width: %(bar_percent)s%"></div></div>', {
				bar_percent: bar_percent,
				msg: msg
			}))
		.appendTo(parent);
}

var msg_dialog=null;
function msgprint(msg, title) {
	if(!msg) return;
	
	if(msg instanceof Array) {
		$.each(msg, function(i,v) {
			if(v) {
				msgprint(v);
			}
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

	// append a <hr> if another msg already exists
	if(msg_dialog.msg_area.html()) msg_dialog.msg_area.append("<hr>");

	msg_dialog.msg_area.append(msg);
	msg_dialog.show();
	
	return msg_dialog;
}

// Floating Message
function show_alert(txt, add_class) {
	if(!$('#dialog-container').length) {
		$('<div id="dialog-container">').appendTo('body');		
	}
	if(!$('#alert-container').length) {
		$('<div id="alert-container"></div>').appendTo('#dialog-container');
	}

	var div = $('<div class="alert">\
		<a class="close">&times;</a>'+ txt +'</div>')
			.appendTo('#alert-container')
			.addClass(add_class);
	div.find('.close').click(function() {
		$(this).parent().remove();
		return false;
	});
	return div;
}