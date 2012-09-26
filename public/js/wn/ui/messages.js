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
},