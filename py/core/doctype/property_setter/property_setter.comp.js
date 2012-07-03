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


$.extend(cur_frm.cscript,{onload:function(doc,dt,dn){cur_frm.cscript.do_setup(doc);},doctype_or_field:function(doc,dt,dn){doc.doc_type=doc.select_item=doc.doc_name=doc.select_doctype='';refresh_many(['doc_type','select_item','doc_name','select_doctype'])},do_setup:function(doc){$c_obj(make_doclist(doc.doctype, doc.name),'get_setup_data','',function(r,rt){var r=r.message;cur_frm.cscript.set_doctypes(r.doctypes);cur_frm.dt_properties={};cur_frm.df_properties={};for(var i=0;i<r.dt_properties.length;i++)
cur_frm.dt_properties[r.dt_properties[i].label]=r.dt_properties[i];for(var i=0;i<r.df_properties.length;i++)
cur_frm.df_properties[r.df_properties[i].label]=r.df_properties[i];if(doc.property){}});},set_doctypes:function(r){var dtl=[];for(var i=0;i<r.length;i++)
dtl.push(get_doctype_label(r[i]))
set_field_options('select_doctype','\n'+dtl.sort().join('\n'))},select_doctype:function(doc,dt,dn){doc.doc_type=get_label_doctype(doc.select_doctype);refresh_field('doc_type');if(doc.doctype_or_field=='DocField')
cur_frm.cscript.set_field_ids(doc);else{doc.doc_name=get_label_doctype(doc.select_doctype);refresh_field('doc_name');cur_frm.cscript.set_properties('DocType')}},set_field_ids:function(doc){$c_obj(make_doclist(doc.doctype, doc.name),'get_field_ids','',function(r,rt){var fl=[];cur_frm.field_id_list=[];for(var i=0;i<r.message.length;i++){var f=r.message[i];fl.push(i+1+'-'+f.label+' ('+f.fieldtype+')');cur_frm.field_id_list.push(f);}
set_field_options('select_item','\n'+fl.join('\n'))});},select_item:function(doc,dt,dn){doc.doc_name=cur_frm.field_id_list[cint(doc.select_item.split('-')[0])-1].name;refresh_many(['doc_name']);cur_frm.cscript.set_properties('DocField');},set_properties:function(dt_or_df){var d=cur_frm[(dt_or_df=='DocType'?'dt_properties':'df_properties')];set_field_options('select_property','\n'+keys(d).sort().join('\n'));doc.property=doc.property_type=doc.default_value='';refresh_many(['property','property_type','default_value']);cur_frm.cscript.load_defaults();},load_defaults:function(){$c_obj([locals[cur_frm.doctype][cur_frm.docname]],'get_defaults','',function(r,rt){cur_frm.ps_doc=r.message;});},select_property:function(doc,dt,dn){var d=cur_frm[(doc.doctype_or_field=='DocType'?'dt_properties':'df_properties')];doc.property=d[doc.select_property].fieldname;doc.property_type=d[doc.select_property].fieldtype;doc.default_value=cstr(cur_frm.ps_doc[doc.property]);refresh_many(['property','property_type','default_value']);},validate:function(doc){if(doc.property_type=='Check'&&!in_list(['0','1'],doc.value)){msgprint('Value for a check field can be either 0 or 1');validated=false;}}})