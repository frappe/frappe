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

cur_frm.cscript['Change Password']= function(doc, cdt, cdn) {
   var error = false;
   if ((!doc.new_password)||(!doc.retype_new_password)){
      alert("Both fields are required!");
      error = true;
   }
   if (doc.new_password.length<4) {
      alert("Password must be atleast 4 characters long");
      error = true;
   }
   if(doc.new_password!=doc.retype_new_password) {
      alert("Passwords must match");
      error = true;
   }
   if(!error) {
      cur_frm.runscript('update_password', '', function(r,t) {
	doc.new_password = '';
	doc.retype_new_password = '';
      });
   }
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
  doc.new_password = '';
  doc.retype_new_password = '';
}