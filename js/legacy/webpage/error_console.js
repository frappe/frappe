// Error Console:

var err_console;
var err_list = [];

function errprint(t) {
	err_list[err_list.length] = ('<pre style="font-family: Courier, Fixed; font-size: 11px; border-bottom: 1px solid #AAA; overflow: auto; width: 90%;">'+t+'</pre>');
}

function setup_err_console() {
	err_console = new Dialog(640, 480, 'Error Console')
	err_console.make_body([
		['HTML', 'Error List']
		,['Button', 'Clear']
		,['HTML', 'Error Report']
	]);
	var span = $a(err_console.widgets['Error Report'], 'span', 'link_type');
	span.innerHTML = 'Send Error Report';
	span.onclick = function() {
		msg = prompt('How / where did you get the error [optional]')
		var call_back = function(r, rt){
			err_console.hide();
			msgprint("Error Report Sent")
		}
		$c('webnotes.utils.send_error_report', {'err_msg': err_console.rows['Error List'].innerHTML, 'msg': msg}, call_back);
	}
	err_console.widgets['Clear'].onclick = function() {
		err_list = [];
		err_console.rows['Error List'].innerHTML = '';
		err_console.hide();
	}
	err_console.onshow = function() {
		err_console.rows['Error List'].innerHTML = '<div style="padding: 16px; height: 360px; width: 90%; overflow: auto;">' 
			+ err_list.join('<div style="height: 10px; margin-bottom: 10px; border-bottom: 1px solid #AAA"></div>') + '</div>';
	}
}

startup_list.push(setup_err_console);
