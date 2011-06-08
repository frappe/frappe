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
	div.innerHTML = '<iframe id="'+id+'" name="'+id+'" src="blank1.html" style="width:0px; height:0px; border:0px"></iframe>';

	// upload form
	var div = $a(parent,'div');
	div.innerHTML = '<form method="POST" enctype="multipart/form-data" action="'+outUrl+'" target="'+id+'"></form>';
	var ul_form = div.childNodes[0];
    
	var f_list = [];
  
	// file data
	var inp_fdata = $a_input($a(ul_form,'span'),'file',{name:'filedata'},{marginLeft:'7px'});

	var inp = $a_input($a(ul_form,'span'),'hidden',{name:'cmd'}); inp.value = 'uploadfile';
	var inp = $a_input($a(ul_form,'span'),'hidden',{name:'uploader_id'}); inp.value = id;
	var inp = $a_input($a(ul_form,'span'),'submit',null,{marginLeft:'7px'}); inp.value = 'Upload';
	
	$y(inp,{width:'80px'});
	$wid_normal(inp);

	inp.onmouseover = function() { $wid_active(this); }
	inp.onmouseout = function() { $wid_normal(this); }
	inp.onmousedown = function() { $wid_pressed(this); }
	inp.onmouseup = function() { $wid_active(inp); }
	
	// dt, dn to show
	for(var key in args) {
		var inp = $a_input($a(ul_form,'span'),'hidden',{name:key}); inp.value = args[key];	
	}
	
	uploaders[id] = this;
}

function upload_callback(id, fid) {
	uploaders[id].callback(fid);
}