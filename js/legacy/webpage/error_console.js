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

// Error Console:

var err_console;
var err_list = [];

function errprint(t) {
	if(!err_list)err_list = [];
	err_list.push('<pre style="font-family: Courier, Fixed; font-size: 11px; \
		border-bottom: 1px solid #AAA; overflow: auto; width: 90%;">'+t+'</pre>');
}

$(document).bind('startup', function() {
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
});
