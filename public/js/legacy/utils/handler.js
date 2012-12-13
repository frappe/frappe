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

function $c(command, args, callback, error, no_spinner, freeze_msg, btn) {
	wn.request.call({
		args: $.extend(args, {cmd: command}),
		success: callback,
		error: error,
		btn: btn,
		freeze: freeze_msg,
		show_spinner: !no_spinner
	})
}

// For calling an object
function $c_obj(doclist, method, arg, callback, no_spinner, freeze_msg, btn) {
	if(arg && typeof arg!='string') arg = JSON.stringify(arg);
		
	args = {
		cmd:'runserverobj',
		arg: arg,
		method: method
	};
	
	if(typeof doclist=='string') 
		args.doctype = doclist; 
	else 
		args.docs = wn.model.compress(doclist)
	
	wn.request.call({
		args: args,
		success: callback,
		btn: btn,
		freeze: freeze_msg,
		show_spinner: !no_spinner
	});
}

// For call a page metho
function $c_page(module, page, method, arg, callback, no_spinner, freeze_msg, btn) {
	if(arg && typeof arg!='string') arg = JSON.stringify(arg);
	wn.request.call({
		args: {
			cmd: module+'.page.'+page+'.'+page+'.'+method,
			arg: arg,
			method: method
		},
		success: callback,
		btn: btn,
		freeze: freeze_msg,
		show_spinner: !no_spinner
	});
}

// For calling an for output as csv
function $c_obj_csv(doclist, method, arg) {
	// single
	
	var args = {}
	args.cmd = 'runserverobj';
	args.as_csv = 1;
	args.method = method;
	args.arg = arg;
	
	if(doclist.substr)
		args.doctype = doclist;		
	else
		args.docs = wn.model.compress(doclist);

	// open
	open_url_post(wn.request.url, args);
}

// call a url as POST
function open_url_post(URL, PARAMS, new_window) {
	var temp=document.createElement("form");
	temp.action=URL;
	temp.method="POST";
	temp.style.display="none";
	if(new_window){
		temp.target = '_blank';
	}
	for(var x in PARAMS) {
		var opt=document.createElement("textarea");
		opt.name=x;
		var val = PARAMS[x];
		if(typeof val!='string') 
			val = JSON.stringify(val);
		opt.value=val;
		temp.appendChild(opt);
	}
	document.body.appendChild(temp);
	temp.submit();
	return temp;
}