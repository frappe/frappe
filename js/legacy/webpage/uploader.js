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

var uploaders = {};
var upload_frame_count = 0;

//
// parent is the element in which you want to add the upload box
// args - additional hidden arguments
// callback - callback function to be called after upload with file id
//
Uploader = function(parent, args, callback) {
	var id = 'frame'+upload_frame_count; upload_frame_count++;
	this.callback = callback;
	
	var div = $a(parent, 'div');
	div.innerHTML = '<iframe id="'+id+'" name="'+id+'" src="blank.html" \
		style="width:0px; height:0px; border:0px"></iframe>';

	// upload form
	var div = $a(parent,'div');
	div.innerHTML = '<form method="POST" enctype="multipart/form-data" action="'+wn.request.url+'" target="'+id+'"></form>';
	var ul_form = div.childNodes[0];
    
	var f_list = [];
  
	// file data
	var inp_fdata = $a_input($a(ul_form,'span'),'file',{name:'filedata'},{marginLeft:'7px'});

	if(!('cmd' in args)) { var inp = $a_input($a(ul_form,'span'),'hidden',{name:'cmd'}); inp.value = 'uploadfile'; }
	var inp = $a_input($a(ul_form,'span'),'hidden',{name:'uploader_id'}); inp.value = id;
	var inp = $a_input($a(ul_form,'span'),'submit',null,{marginLeft:'7px'}); inp.value = 'Upload';
	
	$y(inp,{width:'80px'});
	
	// dt, dn to show
	for(var key in args) {
		var inp = $a_input($a(ul_form,'span'),'hidden',{name:key}); inp.value = args[key];	
	}
	
	uploaders[id] = this;
}

function upload_callback(id, fid) {
	uploaders[id].callback(fid);
}
