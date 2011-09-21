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