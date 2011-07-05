Autosuggest
===========

Adapted from: Timothy Groves - http://www.brandspankingnew.net
   
.. data:: cur_autosug

   Live Autosuggest object
   
.. function:: hide_autosuggest()

   Hide the Live Autosuggest (if exists)

.. class:: AutoSuggest(id, param)

   Create a new autosuggest object

Overriding the default call
---------------------------

* To override the default server call, override the method `doAjaxRequest`
* To override updation in the INPUT element, override the method `custom_select`

Example
-------

Example where email id is to be retrieved::

    // ---- add auto suggest ---- 
    var opts = { script: '', json: true, maxresults: 10 };
    
    var as = new AutoSuggest(d.widgets['To'], opts);
    as.custom_select = function(txt, sel) {
      // ---- add to the last comma ---- 
      var r = '';
      var tl = txt.split(',');
      for(var i=0;i<tl.length-1;i++) r=r+tl[i]+',';
      r = r+(r?' ':'')+sel;
      if(r[r.length-1]==NEWLINE) r=substr(0,r.length-1);
      return r;
    }
    
    // ---- override server call ---- 
    as.doAjaxRequest = function(txt) {
      var pointer = as; var q = '';
      
      // ---- get last few letters typed ---- 
      var last_txt = txt.split(',');
      last_txt = last_txt[last_txt.length-1];
      
      // ---- show options ---- 
      var call_back = function(r,rt) {
        as.aSug = [];
        if(!r.cl) return;
        for (var i=0;i<r.cl.length;i++) {
          as.aSug.push({'id':r.cl[i], 'value':r.cl[i], 'info':''});
        }
        as.createList(as.aSug);
      }
      $c('get_contact_list',{'select':_e.email_as_field, 'from':_e.email_as_dt, 'where':_e.email_as_in, 'txt':(last_txt ? strip(last_txt) : '%')},call_back);
      return;
    }