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

pscript['onload_Login Page'] = function(){
	var lw = $i('login_wrapper');
	$bs(lw, '1px 1px 3px #888');

	$('#login_btn').click(pscript.doLogin)
		
	$('#password').keypress(function(ev){
		if(ev.which==13 && $('#password').val())
			pscript.doLogin();
	})	
}

pscript['onshow_Login Page'] = function() {
	// set banner
}

// Login Callback
pscript.onLoginReply = function(r, rtext) {
	$('#login_btn').done_working();
    if(r.message=="Logged In"){
        window.location.href='index.cgi' + (get_url_arg('page') ? ('?page='+get_url_arg('page')) : '');
    } else {
        $i('login_message').innerHTML = '<span style="color: RED;">'+(r.message)+'</span>';
        //if(r.exc)alert(r.exc);
    }
}


// Login
pscript.doLogin = function(){

    var args = {};
    args['usr']=$i("login_id").value;
    args['pwd']=$i("password").value;
    if($i('remember_me').checked) 
      args['remember_me'] = 1;

	$('#login_btn').set_working();
	
    $c("login", args, pscript.onLoginReply);
}


pscript.show_forgot_password = function(){
    // create dialog
    var d = new Dialog(400, 400, 'Reset Password')
    d.make_body([['HTML','Title','Enter your email id to reset the password'], ['Data','Email Id'], ['Button','Reset']]);

    var callback = function(r,rt) { 
        if(!r.exc) pscript.forgot_dialog.hide();
    }

    d.widgets['Reset'].onclick = function() {
      $c('reset_password', {user: pscript.forgot_dialog.widgets['Email Id'].value}, callback)
    }
    d.show();
    pscript.forgot_dialog = d;
}
