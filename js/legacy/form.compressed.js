
_f.FrmContainer=function(){this.wrapper=page_body.add_page("Forms",function(){},function(){});this.last_displayed=null;$dh(this.wrapper);this.body=$a(this.wrapper,'div','frm_container');_f.frm_dialog=new _f.FrmDialog();}
_f.frm_dialog=null;_f.calling_doc_stack=[];_f.temp_access={};_f.FrmDialog=function(){var me=this;this.last_displayed=null;var d=new Dialog(640,null,'Edit Row');this.body=$a(d.body,'div','dialog_frm');$y(d.body,{backgroundColor:'#EEE'});d.done_btn_area=$a(d.body,'div','',{margin:'8px'});me.on_complete=function(){if(me.table_form){me.dialog.hide();}else{var callback=function(r){var dn=cur_frm.docname;if(!r.exc){me.dialog.hide();}
if(me.on_save_callback)
me.on_save_callback(dn);}
cur_frm.save('Save',callback);}}
d.onshow=function(){d.done_btn_area.innerHTML='';d.done_btn=$btn(d.done_btn_area,'Save',null,null,'green');d.done_btn.onclick=function(){me.on_complete()};if(me.table_form){d.set_title("Editing Row #"+(_f.cur_grid_ridx+1));d.done_btn.innerHTML='Done Editing';}else{d.set_title(cur_frm.doctype==cur_frm.doctype?(cur_frm.doctype):(cur_frm.doctype+': '+cur_frm.docname));d.done_btn.innerHTML='Save';}}
d.onhide=function(){if(_f.cur_grid)
_f.cur_grid.refresh_row(_f.cur_grid_ridx,me.dn);if(page_body.cur_page_label='Forms'){cur_frm=_f.frm_con.cur_frm;}}
this.dialog=d;}
_f.add_frm=function(doctype,onload,opt_name,from_archive){if(frms['DocType']&&frms['DocType'].opendocs[doctype]){msgprint("error:Cannot create an instance of \""+doctype+"\" when the DocType is open.");return;}
if(frms[doctype]){return frms[doctype];}
var callback=function(r,rt){page_body.set_status('Done')
if(!locals['DocType'][doctype]){if(r.exc){msgprint("Did not load "+doctype,1);}
loadpage('_home');return;}
if(r.print_access){if(!_f.temp_access[doctype])
_f.temp_access[doctype]={};_f.temp_access[doctype][opt_name]=1;}
var meta=locals['DocType'][doctype];var in_dialog=false;if(meta.istable)meta.in_dialog=1;if(cint(meta.in_dialog)){var parent=_f.frm_dialog;in_dialog=true;}else{var parent=_f.frm_con;}
var f=new _f.Frm(doctype,parent);f.in_dialog=in_dialog;if(onload)onload(r,rt);}
var is_new=0;if(opt_name&&locals[doctype]&&locals[doctype][opt_name]&&locals[doctype][opt_name].__islocal){is_new=1;}
if(opt_name&&!is_new){var args={'name':opt_name,'doctype':doctype,'getdoctype':1,'user':user};if(get_url_arg('akey'))args['akey']=get_url_arg('akey');if(from_archive)args['from_archive']=1;$c('webnotes.widgets.form.getdoc',args,callback);}else{$c('webnotes.widgets.form.getdoctype',args={'doctype':doctype},callback);}}
_f.FrmHeader=function(parent,frm){var me=this;this.wrapper=$a(parent,'div');if(frm.meta.in_dialog)$y(this.wrapper,{marginLeft:'8px',marginRight:'8px'});this.page_head=new PageHeader(this.wrapper);this.dt_area=$a(this.page_head.main_head,'h1','',{marginRight:'8px',display:'inline'})
var div=$a(null,'div','',{marginBottom:'4px'});this.page_head.lhs.insertBefore(div,this.page_head.sub_head);this.dn_area=$a(div,'span','',{fontSize:'14px',fontWeight:'normal',marginRight:'8px'})
this.status_area=$a(div,'span','',{marginRight:'8px',marginBottom:'2px',cursor:'pointer',textShadow:'none'})
this.timestamp_area=$a($a(div,'div','',{marginTop:'3px'}),'span','field_description',{fontSize:'11px'});}
_f.FrmHeader.prototype.show=function(){$ds(this.wrapper);}
_f.FrmHeader.prototype.hide=function(){$dh(this.wrapper);}
_f.FrmHeader.prototype.refresh=function(){var me=this;var p=cur_frm.get_doc_perms();this.page_head.clear_toolbar();if(cur_frm.meta.read_only_onload&&!cur_frm.doc.__islocal){if(!cur_frm.editable)
this.page_head.add_button('Edit',function(){cur_frm.edit_doc();},1,'ui-icon-document',1);else
this.page_head.add_button('Print View',function(){cur_frm.is_editable[cur_frm.docname]=0;cur_frm.refresh();},1,'ui-icon-document');}
if(cur_frm.editable&&cint(cur_frm.doc.docstatus)==0&&p[WRITE])
this.page_head.add_button('Save',function(){cur_frm.save('Save');},1,'ui-icon-disk',1);if(cint(cur_frm.doc.docstatus)==0&&p[SUBMIT]&&(!cur_frm.doc.__islocal))
this.page_head.add_button('Submit',function(){cur_frm.savesubmit();},0,'ui-icon-locked');if(cint(cur_frm.doc.docstatus)==1&&p[SUBMIT]){this.update_btn=this.page_head.add_button('Update',function(){cur_frm.saveupdate();},1,'ui-icon-disk',1);if(!cur_frm.doc.__unsaved)$dh(this.update_btn);}
if(cint(cur_frm.doc.docstatus)==1&&p[CANCEL])
this.page_head.add_button('Cancel',function(){cur_frm.savecancel()},0,'ui-icon-closethick');if(cint(cur_frm.doc.docstatus)==2&&p[AMEND])
this.page_head.add_button('Amend',function(){cur_frm.amend_doc()},0,'ui-icon-scissors');}
_f.FrmHeader.prototype.show_toolbar=function(){$ds(this.wrapper);this.refresh();}
_f.FrmHeader.prototype.hide_toolbar=function(){$dh(this.wrapper);}
_f.FrmHeader.prototype.refresh_toolbar=function(){var m=cur_frm.meta;if(m.hide_heading||cur_frm.in_dialog){this.hide();}else{this.show();if(m.hide_toolbar){this.hide_toolbar();}else{this.show_toolbar();}}}
_f.FrmHeader.prototype.get_timestamp=function(doc){var scrub_date=function(d){if(d)t=d.split(' ');else return'';return dateutil.str_to_user(t[0])+' '+t[1];}
return repl("Created: %(c_by)s %(c_on)s %(m_by)s %(m_on)s",{c_by:doc.owner,c_on:scrub_date(doc.creation?doc.creation:''),m_by:doc.modified_by?(' | Modified: '+doc.modified_by):'',m_on:doc.modified?('on '+scrub_date(doc.modified)):''});}
_f.FrmHeader.prototype.get_status_tags=function(doc,f){var make_tag=function(label,col){var s=$a(null,'span','',{padding:'2px',backgroundColor:col,color:'#FFF',fontWeight:'bold',marginLeft:(f.meta.issingle?'0px':'8px'),fontSize:'11px'});$(s).css('-moz-border-radius','3px').css('-webkit-border-radius','3px')
s.innerHTML=label;return s;}
var sp1=null;var sp2=null;if(doc.__islocal){label='Unsaved Draft';col='#F81';}else if(cint(doc.__unsaved)){label='Not Saved';col='#F81';if(doc.docstatus==1&&this.update_btn)$ds(this.update_btn);}else if(cint(doc.docstatus)==0){label='Saved';col='#0A1';if(f.get_doc_perms()[SUBMIT]){sp2=make_tag('To Be Submitted','#888');}}else if(cint(doc.docstatus)==1){label='Submitted';col='#44F';}else if(cint(doc.docstatus)==2){label='Cancelled';col='#F44';}
sp1=make_tag(label,col);this.set_in_recent(doc,col);return[sp1,sp2];}
_f.FrmHeader.prototype.set_in_recent=function(doc,col){var tn=$i('rec_'+doc.doctype+'-'+doc.name);if(tn)
$y(tn,{backgroundColor:col});}
_f.FrmHeader.prototype.set_save_submit_color=function(doc){var save_btn=this.page_head.buttons['Save'];var submit_btn=this.page_head.buttons['Submit'];if(cint(doc.docstatus)==0&&submit_btn&&save_btn){if(cint(doc.__unsaved)){save_btn.wid_color='green';submit_btn.wid_color='normal';}else{save_btn.wid_color='normal';submit_btn.wid_color='green';}
$wid_normal(save_btn);$wid_normal(submit_btn);}}
_f.FrmHeader.prototype.refresh_labels=function(f){var ph=this.page_head;var me=this;this.dt_area.innerHTML=get_doctype_label(f.doctype);this.dn_area.innerHTML='';if(!f.meta.issingle)
this.dn_area.innerHTML=f.docname;var doc=locals[f.doctype][f.docname];var sl=this.get_status_tags(doc,f);this.set_save_submit_color(doc);var t=this.status_area;t.innerHTML='';t.appendChild(sl[0]);if(sl[1])t.appendChild(sl[1]);this.timestamp_area.innerHTML=me.get_timestamp(doc);}
_f.edit_record=function(dt,dn){d=_f.frm_dialog;var show_dialog=function(){var f=frms[dt];if(f.meta.istable){f.parent_doctype=cur_frm.doctype;f.parent_docname=cur_frm.docname;}
d.cur_frm=f;d.dn=dn;d.table_form=f.meta.istable;f.refresh(dn);}
if(!frms[dt]){_f.add_frm(dt,show_dialog,null);}else{show_dialog();}}
_f.Frm=function(doctype,parent){this.docname='';this.doctype=doctype;this.display=0;var me=this;this.is_editable={};this.opendocs={};this.cur_section={};this.sections=[];this.sections_by_label={};this.section_count;this.grids=[];this.cscript={};this.pformat={};this.fetch_dict={};this.parent=parent;this.tinymce_id_list=[];frms[doctype]=this;this.setup_meta(doctype);rename_observers.push(this);}
_f.Frm.prototype.setup=function(){var me=this;this.fields=[];this.fields_dict={};this.wrapper=$a(this.parent.body,'div');this.setup_print_layout();this.saved_wrapper=$a(this.wrapper,'div');this.setup_std_layout();this.setup_client_script();this.setup_done=true;}
_f.Frm.prototype.setup_print_layout=function(){this.print_wrapper=$a(this.wrapper,'div');this.print_head=$a(this.print_wrapper,'div');this.print_body=$a(this.print_wrapper,'div','layout_wrapper',{padding:'23px'});var t=make_table(this.print_head,1,2,'100%',[],{padding:'6px'});this.view_btn_wrapper=$a($td(t,0,0),'span','green_buttons');this.view_btn=$btn(this.view_btn_wrapper,'View Details',function(){cur_frm.edit_doc()},{marginRight:'4px'},'green');this.print_btn=$btn($td(t,0,0),'Print',function(){cur_frm.print_doc()});$y($td(t,0,1),{textAlign:'right'});this.print_close_btn=$btn($td(t,0,1),'Close',function(){nav_obj.show_last_open();});}
_f.Frm.prototype.onhide=function(){if(_f.cur_grid_cell)_f.cur_grid_cell.grid.cell_deselect();}
_f.Frm.prototype.setup_std_layout=function(){this.page_layout=new wn.PageLayout({parent:this.wrapper,main_width:this.in_dialog?'100%':'75%',sidebar_width:this.in_dialog?'0%':'25%'})
this.tip_wrapper=$a(this.page_layout.toolbar_area,'div');this.meta.section_style='Simple';this.layout=new Layout(this.page_layout.body,'100%');if(!this.in_dialog){this.setup_sidebar();}
this.setup_footer();if(!(this.meta.istable||user=='Guest'))this.frm_head=new _f.FrmHeader(this.page_layout.head,this);if(this.frm_head&&this.meta.in_dialog)$dh(this.frm_head.page_head.close_btn);this.setup_tips();if(this.meta.colour)
this.layout.wrapper.style.backgroundColor='#'+this.meta.colour.split(':')[1];this.setup_fields_std();}
_f.Frm.prototype.setup_print=function(){var fl=getchildren('DocFormat',this.meta.name,'formats','DocType');var l=[];this.default_format='Standard';if(fl.length){this.default_format=fl[0].format;for(var i=0;i<fl.length;i++)
l.push(fl[i].format);}
l.push('Standard');this.print_sel=$a(null,'select','',{width:'160px'});add_sel_options(this.print_sel,l);this.print_sel.value=this.default_format;}
_f.Frm.prototype.print_doc=function(){if(this.doc.docstatus==2){msgprint("Cannot Print Cancelled Documents.");return;}
_p.show_dialog();}
_f.Frm.prototype.email_doc=function(){if(!_e.dialog)_e.make();sel=this.print_sel;var c=$td(_e.dialog.rows['Format'].tab,0,1);if(c.cur_sel){c.removeChild(c.cur_sel);c.cur_sel=null;}
c.appendChild(this.print_sel);c.cur_sel=this.print_sel;_e.dialog.widgets['Send With Attachments'].checked=0;if(cur_frm.doc.file_list){$ds(_e.dialog.rows['Send With Attachments']);}else{$dh(_e.dialog.rows['Send With Attachments']);}
_e.dialog.widgets['Subject'].value=get_doctype_label(this.meta.name)+': '+this.docname;_e.dialog.show();}
_f.Frm.prototype.rename_notify=function(dt,old,name){if(this.doctype!=dt)return;this.cur_section[name]=this.cur_section[old];delete this.cur_section[old];this.is_editable[name]=this.is_editable[old];delete this.is_editable[old];if(this.docname==old)
this.docname=name;if(this&&this.opendocs[old]){local_dt[dt][name]=local_dt[dt][old];local_dt[dt][old]=null;}
this.opendocs[old]=false;this.opendocs[name]=true;}
_f.Frm.prototype.set_heading=function(){if(!this.meta.istable&&this.frm_head)this.frm_head.refresh_labels(this);}
_f.Frm.prototype.set_section=function(sec_id){if(!this.sections[sec_id]||!this.sections[sec_id].expand)
return;if(this.sections[this.cur_section[this.docname]])
this.sections[this.cur_section[this.docname]].collapse();this.sections[sec_id].expand();this.cur_section[this.docname]=sec_id;}
_f.Frm.prototype.setup_tips=function(){var me=this;this.tip_box=$a(this.tip_wrapper,'div','help_box');var tab=$a(this.tip_box,'table');var r=tab.insertRow(0);var c0=r.insertCell(0);this.c1=r.insertCell(1);this.img=$a(c0,'img');this.img.setAttribute('src','images/icons/lightbulb.gif');c0.style.width='24px';this.set_tip=function(t,icon){me.c1.innerHTML='<div style="margin-bottom: 8px;">'+t+'</div>';$ds(me.tip_box);if(icon)this.img.setAttribute('src','images/icons/'+icon);}
this.append_tip=function(t){me.c1.innerHTML+='<div style="margin-bottom: 8px;">'+t+'</div>';$ds(me.tip_box);}
this.clear_tip=function(){me.c1.innerHTML='';$dh(me.tip_box);}
$dh(this.tip_box);}
_f.Frm.prototype.setup_meta=function(){this.meta=get_local('DocType',this.doctype);this.perm=get_perm(this.doctype);this.setup_print();}
_f.Frm.prototype.setup_sidebar=function(){this.sidebar=new wn.widgets.form.sidebar.Sidebar(this);}
_f.Frm.prototype.setup_footer=function(){var me=this;var f=this.page_layout.footer;f.save_area=$a(this.page_layout.footer,'div','',{display:'none'});f.help_area=$a(this.page_layout.footer,'div');var b=$btn(f.save_area,'Save',function(){cur_frm.save('Save');},{marginLeft:'0px'},'green');f.show_save=function(){$ds(me.page_layout.footer.save_area);}
f.hide_save=function(){$dh(me.page_layout.footer.save_area);}}
_f.Frm.prototype.setup_fields_std=function(){var fl=fields_list[this.doctype];fl.sort(function(a,b){return a.idx-b.idx});if(fl[0]&&fl[0].fieldtype!="Section Break"||get_url_arg('embed')){this.layout.addrow();if(fl[0].fieldtype!="Column Break"){var c=this.layout.addcell();$y(c.wrapper,{padding:'8px'});}}
var sec;for(var i=0;i<fl.length;i++){var f=fl[i];if(get_url_arg('embed')&&(in_list(['Section Break','Column Break'],f.fieldtype)))continue;if(f.fieldtype=='Section Break'&&fl[i+1]&&fl[i+1].fieldtype=='Section Break')continue;var fn=f.fieldname?f.fieldname:f.label;var fld=make_field(f,this.doctype,this.layout.cur_cell,this);this.fields[this.fields.length]=fld;this.fields_dict[fn]=fld;if(this.meta.section_style!='Simple')
fld.parent_section=sec;if(f.fieldtype=='Section Break'&&f.options!='Simple')
sec=fld;if((f.fieldtype=='Section Break')&&(fl[i+1])&&(fl[i+1].fieldtype!='Column Break')){var c=this.layout.addcell();$y(c.wrapper,{padding:'8px'});}}}
_f.Frm.prototype.add_custom_button=function(label,fn,icon){this.frm_head.page_head.add_button(label,fn,1);}
_f.Frm.prototype.clear_custom_buttons=function(){}
_f.Frm.prototype.add_fetch=function(link_field,src_field,tar_field){if(!this.fetch_dict[link_field]){this.fetch_dict[link_field]={'columns':[],'fields':[]}}
this.fetch_dict[link_field].columns.push(src_field);this.fetch_dict[link_field].fields.push(tar_field);}
_f.Frm.prototype.setup_client_script=function(){if(this.meta.client_script_core||this.meta.client_script||this.meta.__js){this.runclientscript('setup',this.doctype,this.docname);}}
_f.Frm.prototype.set_parent=function(parent){if(parent){this.parent=parent;if(this.wrapper&&this.wrapper.parentNode!=parent)
parent.appendChild(this.wrapper);}}
_f.Frm.prototype.refresh_print_layout=function(){$ds(this.print_wrapper);$dh(this.page_layout.wrapper);var me=this;var print_callback=function(print_html){me.print_body.innerHTML=print_html;}
if(cur_frm.doc.select_print_heading)
cur_frm.set_print_heading(cur_frm.doc.select_print_heading)
if(user!='Guest'){$di(this.view_btn_wrapper);if(cur_frm.doc.__archived){$dh(this.view_btn_wrapper);}}else{$dh(this.view_btn_wrapper);$dh(this.print_close_btn);}
_p.build(this.default_format,print_callback,null,1);}
_f.Frm.prototype.hide=function(){$dh(this.wrapper);this.display=0;hide_autosuggest();}
_f.Frm.prototype.show_the_frm=function(){if(this.parent.last_displayed&&this.parent.last_displayed!=this){this.parent.last_displayed.defocus_rest();this.parent.last_displayed.hide();}
if(this.wrapper&&this.wrapper.style.display.toLowerCase()=='none'){$ds(this.wrapper);this.display=1;}
if(this.meta.in_dialog&&!this.parent.dialog.display){if(!this.meta.istable)
this.parent.table_form=false;this.parent.dialog.show();}
this.parent.last_displayed=this;}
_f.Frm.prototype.set_print_heading=function(txt){this.pformat[cur_frm.docname]=txt;}
_f.Frm.prototype.defocus_rest=function(){mclose();if(_f.cur_grid_cell)_f.cur_grid_cell.grid.cell_deselect();cur_page=null;}
_f.Frm.prototype.get_doc_perms=function(){var p=[0,0,0,0,0,0];for(var i=0;i<this.perm.length;i++){if(this.perm[i]){if(this.perm[i][READ])p[READ]=1;if(this.perm[i][WRITE])p[WRITE]=1;if(this.perm[i][SUBMIT])p[SUBMIT]=1;if(this.perm[i][CANCEL])p[CANCEL]=1;if(this.perm[i][AMEND])p[AMEND]=1;}}
return p;}
_f.Frm.prototype.refresh_header=function(){if(!this.meta.in_dialog){set_title(this.meta.issingle?this.doctype:this.docname);}
if(this.frm_head)this.frm_head.refresh_toolbar();if(page_body.wntoolbar)page_body.wntoolbar.rdocs.add(this.doctype,this.docname,1);this.set_heading();}
_f.Frm.prototype.check_doc_perm=function(){var dt=this.parent_doctype?this.parent_doctype:this.doctype;var dn=this.parent_docname?this.parent_docname:this.docname;this.perm=get_perm(dt,dn);this.orig_perm=get_perm(dt,dn,1);if(!this.perm[0][READ]){if(user=='Guest'){if(_f.temp_access[dt]&&_f.temp_access[dt][dn]){this.perm=[[1,0,0]]
return 1;}}
nav_obj.show_last_open();return 0;}
return 1}
_f.Frm.prototype.refresh=function(docname){if(docname){if(this.docname!=docname&&!this.meta.in_dialog&&!this.meta.istable)scroll(0,0);this.docname=docname;}
if(!this.meta.istable){cur_frm=this;this.parent.cur_frm=this;}
if(this.docname){if(!this.check_doc_perm())return;if(!this.setup_done)this.setup();this.runclientscript('set_perm',this.doctype,this.docname);this.doc=get_local(this.doctype,this.docname);var is_onload=false;if(!this.opendocs[this.docname]){is_onload=true;this.setnewdoc(this.docname);}
if(this.doc.__islocal)
this.is_editable[this.docname]=1;this.editable=this.is_editable[this.docname];if(!this.doc.__archived&&(this.editable||(!this.editable&&this.meta.istable))){if(this.print_wrapper){$dh(this.print_wrapper);$ds(this.page_layout.wrapper);}
if(!this.meta.istable){this.refresh_header();this.sidebar&&this.sidebar.refresh();}
this.runclientscript('refresh');$(document).trigger('form_refresh')
this.refresh_tabs();this.refresh_fields();this.refresh_dependency();this.refresh_footer();if(this.layout)this.layout.show();if(is_onload)
this.runclientscript('onload_post_render',this.doctype,this.docname);}else{this.refresh_header();if(this.print_wrapper){this.refresh_print_layout();}
this.runclientscript('edit_status_changed');}
if(!this.display)this.show_the_frm();if(!this.meta.in_dialog)page_body.change_to('Forms');}}
_f.Frm.prototype.refresh_tabs=function(){var me=this;if(me.meta.section_style=='Tray'||me.meta.section_style=='Tabbed'){for(var i in me.sections){me.sections[i].collapse();}
me.set_section(me.cur_section[me.docname]);}}
_f.Frm.prototype.refresh_footer=function(){var f=this.page_layout.footer;if(f.save_area){if(get_url_arg('embed')||(this.editable&&!this.meta.in_dialog&&this.doc.docstatus==0&&!this.meta.istable&&this.get_doc_perms()[WRITE])){f.show_save();}else{f.hide_save();}}}
_f.Frm.prototype.refresh_fields=function(){for(var i=0;i<this.fields.length;i++){var f=this.fields[i];f.perm=this.perm;f.docname=this.docname;if(f.refresh)f.refresh();}
this.cleanup_refresh(this);}
_f.Frm.prototype.cleanup_refresh=function(){var me=this;if(me.fields_dict['amended_from']){if(me.doc.amended_from){unhide_field('amended_from');unhide_field('amendment_date');}else{hide_field('amended_from');hide_field('amendment_date');}}
if(me.fields_dict['trash_reason']){if(me.doc.trash_reason&&me.doc.docstatus==2){unhide_field('trash_reason');}else{hide_field('trash_reason');}}
if(me.meta.autoname&&me.meta.autoname.substr(0,6)=='field:'&&!me.doc.__islocal){var fn=me.meta.autoname.substr(6);set_field_permlevel(fn,1);}}
_f.Frm.prototype.refresh_dependency=function(){var me=this;var doc=locals[this.doctype][this.docname];var dep_dict={};var has_dep=false;for(fkey in me.fields){var f=me.fields[fkey];f.dependencies_clear=true;var guardian=f.df.depends_on;if(guardian){if(!dep_dict[guardian])
dep_dict[guardian]=[];dep_dict[guardian][dep_dict[guardian].length]=f;has_dep=true;}}
if(!has_dep)return;for(var i=me.fields.length-1;i>=0;i--){var f=me.fields[i];f.guardian_has_value=true;if(f.df.depends_on){var v=doc[f.df.depends_on];if(f.df.depends_on.substr(0,5)=='eval:'){f.guardian_has_value=eval(f.df.depends_on.substr(5));}else if(f.df.depends_on.substr(0,3)=='fn:'){f.guardian_has_value=me.runclientscript(f.df.depends_on.substr(3),me.doctype,me.docname);}else{if(v||(v==0&&!v.substr)){}else{f.guardian_has_value=false;}}
if(f.guardian_has_value){if(f.grid)f.grid.show();else $ds(f.wrapper);}else{if(f.grid)f.grid.hide();else $dh(f.wrapper);}}}}
_f.Frm.prototype.setnewdoc=function(docname){if(this.opendocs[docname]){this.docname=docname;return;}
Meta.make_local_dt(this.doctype,docname);this.docname=docname;var me=this;var viewname=docname;if(this.meta.issingle)viewname=this.doctype;var iconsrc='page.gif';if(this.meta.smallicon)
iconsrc=this.meta.smallicon;this.runclientscript('onload',this.doctype,this.docname);this.is_editable[docname]=1;if(this.meta.read_only_onload)this.is_editable[docname]=0;if(this.meta.section_style=='Tray'||this.meta.section_style=='Tabbed'){this.cur_section[docname]=0;}
this.opendocs[docname]=true;}
_f.Frm.prototype.edit_doc=function(){this.is_editable[this.docname]=true;this.refresh();}
_f.Frm.prototype.show_doc=function(dn){this.refresh(dn);}
var validated;_f.Frm.prototype.save=function(save_action,call_back){if(!save_action)save_action='Save';var me=this;if(this.savingflag){msgprint("Document is currently saving....");return;}
if(save_action=='Submit'){locals[this.doctype][this.docname].submitted_on=dateutil.full_str();locals[this.doctype][this.docname].submitted_by=user;}
if(save_action=='Trash'){var reason=prompt('Reason for trash (mandatory)','');if(!strip(reason)){msgprint('Reason is mandatory, not trashed');return;}
locals[this.doctype][this.docname].trash_reason=reason;}
if(save_action=='Cancel'){var reason=prompt('Reason for cancellation (mandatory)','');if(!strip(reason)){msgprint('Reason is mandatory, not cancelled');return;}
locals[this.doctype][this.docname].cancel_reason=reason;locals[this.doctype][this.docname].cancelled_on=dateutil.full_str();locals[this.doctype][this.docname].cancelled_by=user;}else if(save_action=='Update'){}else{validated=true;if(this.cscript.validate)
this.runclientscript('validate',this.doctype,this.docname);if(!validated){this.savingflag=false;return'Error';}}
var ret_fn=function(r){if(user=='Guest'&&!r.exc){$dh(me.page_layout.wrapper);$ds(me.saved_wrapper);me.saved_wrapper.innerHTML='<div style="padding: 150px 16px; text-align: center; font-size: 14px;">'
+(cur_frm.message_after_save?cur_frm.message_after_save:'Your information has been sent. Thank you!')
+'</div>';return;}
if(!me.meta.istable){me.refresh();}
if(call_back){if(call_back=='home'){loadpage('_home');return;}
call_back(r);}}
var me=this;var ret_fn_err=function(r){var doc=locals[me.doctype][me.docname];me.savingflag=false;ret_fn(r);}
this.savingflag=true;if(this.docname&&validated){scroll(0,0);return this.savedoc(save_action,ret_fn,ret_fn_err);}}
_f.Frm.prototype.runscript=function(scriptname,callingfield,onrefresh){var me=this;if(this.docname){var doclist=compress_doclist(make_doclist(this.doctype,this.docname));if(callingfield)callingfield.input.disabled=true;$c('runserverobj',{'docs':doclist,'method':scriptname},function(r,rtxt){if(onrefresh)
onrefresh(r,rtxt);me.refresh_fields();me.refresh_dependency();if(callingfield)callingfield.input.done_working();});}}
_f.Frm.prototype.runclientscript=function(caller,cdt,cdn){var _dt=this.parent_doctype?this.parent_doctype:this.doctype;var _dn=this.parent_docname?this.parent_docname:this.docname;var doc=get_local(_dt,_dn);if(!cdt)cdt=this.doctype;if(!cdn)cdn=this.docname;var ret=null;try{if(this.cscript[caller])
ret=this.cscript[caller](doc,cdt,cdn);if(this.cscript['custom_'+caller])
ret+=this.cscript['custom_'+caller](doc,cdt,cdn);}catch(e){submit_error(e);}
if(caller&&caller.toLowerCase()=='setup'){var doctype=get_local('DocType',this.doctype);var cs=doctype.__js||(doctype.client_script_core+doctype.client_script);if(cs){try{var tmp=eval(cs);}catch(e){submit_error(e);}}
if(doctype.__css)set_style(doctype.__css)
if(doctype.client_string){this.cstring={};var elist=doctype.client_string.split('---');for(var i=1;i<elist.length;i=i+2){this.cstring[strip(elist[i])]=elist[i+1];}}}
return ret;}
_f.Frm.prototype.copy_doc=function(onload,from_amend){if(!this.perm[0][CREATE]){msgprint('You are not allowed to create '+this.meta.name);return;}
var dn=this.docname;var newdoc=LocalDB.copy(this.doctype,dn,from_amend);if(this.meta.allow_attach&&newdoc.file_list)
newdoc.file_list=null;var dl=make_doclist(this.doctype,dn);var tf_dict={};for(var d in dl){d1=dl[d];if(!tf_dict[d1.parentfield]){tf_dict[d1.parentfield]=get_field(d1.parenttype,d1.parentfield);}
if(d1.parent==dn&&cint(tf_dict[d1.parentfield].no_copy)!=1){var ch=LocalDB.copy(d1.doctype,d1.name,from_amend);ch.parent=newdoc.name;ch.docstatus=0;ch.owner=user;ch.creation='';ch.modified_by=user;ch.modified='';}}
newdoc.__islocal=1;newdoc.docstatus=0;newdoc.owner=user;newdoc.creation='';newdoc.modified_by=user;newdoc.modified='';if(onload)onload(newdoc);loaddoc(newdoc.doctype,newdoc.name);}
_f.Frm.prototype.reload_doc=function(){var me=this;if(frms['DocType']&&frms['DocType'].opendocs[me.doctype]){msgprint("error:Cannot refresh an instance of \""+me.doctype+"\" when the DocType is open.");return;}
var ret_fn=function(r,rtxt){page_body.set_status('Done')
me.runclientscript('setup',me.doctype,me.docname);me.refresh();}
page_body.set_status('Reloading...')
if(me.doc.__islocal){$c('webnotes.widgets.form.getdoctype',{'doctype':me.doctype},ret_fn,null,null,'Refreshing '+me.doctype+'...');}else{var gl=me.grids;for(var i=0;i<gl.length;i++){var dt=gl[i].df.options;for(var dn in locals[dt]){if(locals[dt][dn].__islocal&&locals[dt][dn].parent==me.docname){var d=locals[dt][dn];d.parent='';d.docstatus=2;d.__deleted=1;}}}
$c('webnotes.widgets.form.getdoc',{'name':me.docname,'doctype':me.doctype,'getdoctype':1,'user':user},ret_fn,null,null,'Refreshing '+me.docname+'...');}}
_f.Frm.prototype.savedoc=function(save_action,onsave,onerr){this.error_in_section=0;save_doclist(this.doctype,this.docname,save_action,onsave,onerr);}
_f.Frm.prototype.saveupdate=function(){this.save('Update');}
_f.Frm.prototype.savesubmit=function(){var answer=confirm("Permanently Submit "+this.docname+"?");if(answer)this.save('Submit');}
_f.Frm.prototype.savecancel=function(){var answer=confirm("Permanently Cancel "+this.docname+"?");if(answer)this.save('Cancel');}
_f.Frm.prototype.savetrash=function(){var me=this;var answer=confirm("Permanently Delete "+this.docname+"? This action cannot be reversed");if(answer){$c('webnotes.model.delete_doc',{dt:this.doctype,dn:this.docname},function(r,rt){if(r.message=='okay'){LocalDB.delete_doc(me.doctype,me.docname);if(page_body.wntoolbar)page_body.wntoolbar.rdocs.remove(me.doctype,me.docname);nav_obj.show_last_open();}})}}
_f.Frm.prototype.amend_doc=function(){if(!this.fields_dict['amended_from']){alert('"amended_from" field must be present to do an amendment.');return;}
var me=this;var fn=function(newdoc){newdoc.amended_from=me.docname;if(me.fields_dict&&me.fields_dict['amendment_date'])
newdoc.amendment_date=dateutil.obj_to_str(new Date());}
this.copy_doc(fn,1);}
_f.get_value=function(dt,dn,fn){if(locals[dt]&&locals[dt][dn])
return locals[dt][dn][fn];}
_f.set_value=function(dt,dn,fn,v){var d=locals[dt][dn];if(!d){errprint('error:Trying to set a value for "'+dt+','+dn+'" which is not found');return;}
var changed=d[fn]!=v;if(changed&&(d[fn]==null||v==null)&&(cstr(d[fn])==cstr(v)))changed=0;if(changed){d[fn]=v;d.__unsaved=1;var frm=frms[d.doctype];try{if(d.parent&&d.parenttype){locals[d.parenttype][d.parent].__unsaved=1;frm=frms[d.parenttype];}}catch(e){if(d.parent&&d.parenttype)
errprint('Setting __unsaved error:'+d.name+','+d.parent+','+d.parenttype);}
if(frm&&frm==cur_frm){frm.set_heading();}}}
_f.Frm.prototype.show_comments=function(){if(!cur_frm.comments){cur_frm.comments=new Dialog(540,400,'Comments');cur_frm.comments.comment_body=$a(cur_frm.comments.body,'div','dialog_frm');$y(cur_frm.comments.body,{backgroundColor:'#EEE'});cur_frm.comments.list=new CommentList(cur_frm.comments.comment_body);}
cur_frm.comments.list.dt=cur_frm.doctype;cur_frm.comments.list.dn=cur_frm.docname;cur_frm.comments.show();cur_frm.comments.list.run();}
_f.ColumnBreak=function(){this.set_input=function(){};}
_f.ColumnBreak.prototype.make_body=function(){if((!this.perm[this.df.permlevel])||(!this.perm[this.df.permlevel][READ])||this.df.hidden){return;}
this.cell=this.frm.layout.addcell(this.df.width);$y(this.cell.wrapper,{padding:'8px'});_f.cur_col_break_width=this.df.width;var fn=this.df.fieldname?this.df.fieldname:this.df.label;if(this.df&&this.df.label){this.label=$a(this.cell.wrapper,'h3','','',this.df.label);}}
_f.ColumnBreak.prototype.refresh=function(layout){if(!this.cell)return;var fn=this.df.fieldname?this.df.fieldname:this.df.label;if(fn){this.df=get_field(this.doctype,fn,this.docname);if(this.set_hidden!=this.df.hidden){if(this.df.hidden)
this.cell.hide();else
this.cell.show();this.set_hidden=this.df.hidden;}}}
_f.SectionBreak=function(){this.set_input=function(){};}
_f.SectionBreak.prototype.make_row=function(){this.row=this.df.label?this.frm.layout.addrow():this.frm.layout.addsubrow();}
_f.SectionBreak.prototype.make_collapsible=function(head){var me=this;var div=$a(head,'div','',{paddingBottom:'3px',borderBottom:'1px solid #AAA'});if(cur_frm.meta.in_dialog)$y(div,{marginLeft:'8px'});this.chk=$a_input(div,'checkbox',null,{marginRight:'8px'})
if(this.df.label){this.label=$a(div,'h3','',{display:'inline'},this.df.label);}
var d=this.df.description;if(d){this.desc_area=$a(div,'span','field_description',{marginLeft:'8px'});this.desc_area.innerHTML=d.substr(0,50)+(d.length>50?'...':'');}
var span=$a(div,'div','wn-icon ic-arrow_top',{cssFloat:'right',marginRight:'8px',cursor:'pointer',marginTop:'7px'})
span.title='Go to top';span.onclick=function(){scroll(0,0);}
this.chk.onclick=function(){if(this.checked)me.expand();else me.collapse();}
this.expand=function(){$(me.row.main_body).slideDown();}
this.collapse=function(){$(me.row.main_body).slideUp();}
if(me.frm.section_count){$dh(this.row.main_body);}else{this.chk.checked=true;}}
_f.SectionBreak.prototype.make_simple_section=function(with_header){this.wrapper=$a(this.row.main_head,'div','',{margin:'8px 8px 0px 0px'});var me=this;if(this.df.colour){var col=this.df.colour.split(':')[1];if(col!='FFF'){$y(this.row.sub_wrapper,{margin:'8px',padding:'0px',backgroundColor:('#'+col)});}}
if(with_header){if(this.df.label&&this.df.options!='Simple'){this.make_collapsible(this.wrapper);}else{$y(this.wrapper,{paddingBottom:'4px'});if(this.df.label){$a(this.wrapper,'h3','',{},this.df.label);}}}
$y(this.row.body,{marginLeft:'17px'});}
_f.SectionBreak.prototype.add_to_sections=function(){this.sec_id=this.frm.sections.length;this.frm.sections[this.sec_id]=this;this.frm.sections_by_label[this.df.label]=this;}
_f.cur_sec_header=null;_f.SectionBreak.prototype.make_body=function(){if((!this.perm[this.df.permlevel])||(!this.perm[this.df.permlevel][READ])||this.df.hidden){return;}
var me=this;if(this.df){this.make_row();this.make_simple_section(1,1);}}
_f.SectionBreak.prototype.refresh=function(layout){var fn=this.df.fieldname?this.df.fieldname:this.df.label;if(fn)
this.df=get_field(this.doctype,fn,this.docname);if(this.set_hidden!=this.df.hidden){if(this.df.hidden){if(this.frm.meta.section_style=='Tabbed'){$dh(this.mytab);}else if(this.tray_item)
this.tray_item.hide();if(this.row)this.row.hide();}else{if(this.frm.meta.section_style=='Tabbed'){$di(this.mytab);}else if(this.tray_item)
this.tray_item.show();if(this.expanded)this.row.show();}
this.set_hidden=this.df.hidden;}}
_f.ImageField=function(){this.images={};}
_f.ImageField.prototype=new Field();_f.ImageField.prototype.onmake=function(){this.no_img=$a(this.wrapper,'div','no_img');this.no_img.innerHTML="No Image";$dh(this.no_img);}
_f.ImageField.prototype.get_image_src=function(doc){if(doc.file_list){file=doc.file_list.split(',');extn=file[0].split('.');extn=extn[extn.length-1].toLowerCase();var img_extn_list=['gif','jpg','bmp','jpeg','jp2','cgm','ief','jpm','jpx','png','tiff','jpe','tif'];if(in_list(img_extn_list,extn)){var src=outUrl+"?cmd=downloadfile&file_id="+file[1];}}else{var src="";}
return src;}
_f.ImageField.prototype.onrefresh=function(){var me=this;if(!this.images[this.docname])this.images[this.docname]=$a(this.wrapper,'img');else $di(this.images[this.docname]);var img=this.images[this.docname]
for(var dn in this.images)if(dn!=this.docname)$dh(this.images[dn]);var doc=locals[this.frm.doctype][this.frm.docname];if(!this.df.options)var src=this.get_image_src(doc);else var src=outUrl+'?cmd=get_file&fname='+this.df.options+"&__account="+account_id+(__sid150?("&sid150="+__sid150):'');if(src){$dh(this.no_img);if(img.getAttribute('src')!=src)img.setAttribute('src',src);canvas=this.wrapper;canvas.img=this.images[this.docname];canvas.style.overflow="auto";$w(canvas,"100%");if(!this.col_break_width)this.col_break_width='100%';var allow_width=cint(1000*(cint(this.col_break_width)-10)/100);if((!img.naturalWidth)||cint(img.naturalWidth)>allow_width)
$w(img,allow_width+'px');}else{$ds(this.no_img);}}
_f.ImageField.prototype.set_disp=function(val){}
_f.ImageField.prototype.set=function(val){}
_f.ButtonField=function(){};_f.ButtonField.prototype=new Field();_f.ButtonField.prototype.with_label=0;_f.ButtonField.prototype.init=function(){this.prev_button=null;if(!this.frm)return;if(cur_frm&&cur_frm.fields[cur_frm.fields.length-1]&&cur_frm.fields[cur_frm.fields.length-1].df.fieldtype=='Button'){this.make_body=function(){this.prev_button=cur_frm.fields[cur_frm.fields.length-1];if(!this.prev_button.prev_button){this.prev_button.button_area=$a(this.prev_button.input_area,'span');}
this.wrapper=this.prev_button.wrapper;this.input_area=this.prev_button.input_area;this.disp_area=this.prev_button.disp_area;this.button_area=$a(this.prev_button.input_area,'span');}}}
_f.ButtonField.prototype.make_input=function(){var me=this;if(!this.prev_button){$y(this.input_area,{marginTop:'4px',marginBottom:'4px'});}
if(!this.button_area)this.button_area=$a(this.input_area,'span','',{marginRight:'4px'});this.input=$btn(this.button_area,me.df.label.substr(0,20)+((me.df.label.length>20)?'..':''),{width:'170px',fontWeight:'bold'},null,1)
this.input.onclick=function(){if(me.not_in_form)return;this.set_disabled();if(cur_frm.cscript[me.df.label]&&(!me.in_filter)){cur_frm.runclientscript(me.df.label,me.doctype,me.docname);this.set_enabled();}else{this.set_working();cur_frm.runscript(me.df.options,me);}}}
_f.ButtonField.prototype.hide=function(){$dh(this.button_area);};_f.ButtonField.prototype.show=function(){$ds(this.button_area);};_f.ButtonField.prototype.set=function(v){};_f.ButtonField.prototype.set_disp=function(val){}
_f.TableField=function(){};_f.TableField.prototype=new Field();_f.TableField.prototype.with_label=0;_f.TableField.prototype.make_body=function(){if(this.perm[this.df.permlevel]&&this.perm[this.df.permlevel][READ]){if(this.df.description){this.desc_area=$a(this.parent,'div','field_description','',this.df.description)}
this.grid=new _f.FormGrid(this);if(this.frm)this.frm.grids[this.frm.grids.length]=this;this.grid.make_buttons();}}
_f.TableField.prototype.refresh=function(){if(!this.grid)return;var st=this.get_status();if(!this.df['default'])
this.df['default']='';this.grid.can_add_rows=false;this.grid.can_edit=false
if(st=='Write'){if(cur_frm.editable&&this.perm[this.df.permlevel]&&this.perm[this.df.permlevel][WRITE]){this.grid.can_edit=true;if(this.df['default'].toLowerCase()!='no toolbar')
this.grid.can_add_rows=true;}
if(cur_frm.editable&&this.df.allow_on_submit&&cur_frm.doc.docstatus==1&&this.df['default'].toLowerCase()!='no toolbar'){this.grid.can_add_rows=true;this.grid.can_edit=true;}}
if(this.old_status!=st){if(st=='Write'){this.grid.show();}else if(st=='Read'){this.grid.show();}else{this.grid.hide();}
this.old_status=st;}
this.grid.refresh();}
_f.TableField.prototype.set=function(v){};_f.TableField.prototype.set_input=function(v){};_f.CodeField=function(){};_f.CodeField.prototype=new Field();_f.CodeField.prototype.make_input=function(){var me=this;this.label_span.innerHTML=this.df.label;this.input=$a(this.input_area,'textarea','code_text',{fontSize:'12px'});this.myid=wn.dom.set_unique_id(this.input);this.input.setAttribute('wrap','off');this.input.set_input=function(v){if(me.editor){me.editor.setContent(v);}else{me.input.value=v;me.input.innerHTML=v;}}
this.input.onchange=function(){if(me.editor){}else{me.set(me.input.value);}
me.run_trigger();}
this.get_value=function(){if(me.editor){return me.editor.getContent();}else{return this.input.value;}}
if(this.df.fieldtype=='Text Editor'){$(me.input).tinymce({script_url:'js/tiny_mce_33/tiny_mce.js',theme:"advanced",plugins:"style,inlinepopups,table",extended_valid_elements:"div[id|dir|class|align|style]",width:'100%',height:'360px',theme_advanced_buttons1:"bold,italic,underline,strikethrough,hr,|,justifyleft,justifycenter,justifyright,|,formatselect,fontselect,fontsizeselect",theme_advanced_buttons2:"bullist,numlist,|,outdent,indent,|,undo,redo,|,link,unlink,code,|,forecolor,backcolor,|,tablecontrols",theme_advanced_buttons3:"",theme_advanced_toolbar_location:"top",theme_advanced_toolbar_align:"left",content_css:"js/tiny_mce_33/custom_content.css",oninit:function(){me.init_editor();}});}else{$y(me.input,{fontFamily:'Courier, Fixed'});}}
_f.CodeField.prototype.init_editor=function(){var me=this;this.editor=tinymce.get(this.myid);this.editor.onKeyUp.add(function(ed,e){me.set(ed.getContent());});this.editor.onPaste.add(function(ed,e){me.set(ed.getContent());});this.editor.onSetContent.add(function(ed,e){me.set(ed.getContent());});var c=locals[cur_frm.doctype][cur_frm.docname][this.df.fieldname];if(cur_frm&&c){this.editor.setContent(c);}}
_f.CodeField.prototype.set_disp=function(val){$y(this.disp_area,{width:'90%'})
if(this.df.fieldtype=='Text Editor'){this.disp_area.innerHTML=val;}else{this.disp_area.innerHTML='<textarea class="code_text" readonly=1>'+val+'</textarea>';}}
_f.cur_grid_cell=null;_f.Grid=function(parent){}
_f.Grid.prototype.init=function(parent,row_height){this.col_idx_by_name={}
this.alt_row_bg='#F2F2FF';this.row_height=row_height;if(!row_height)this.row_height='26px';this.make_ui(parent);this.insert_column('','','Int','Sr','50px','',[1,0,0]);if(this.oninit)this.oninit();keypress_observers.push(this);}
_f.Grid.prototype.make_ui=function(parent){var ht=make_table($a(parent,'div'),1,2,'100%',['60%','40%']);this.main_title=$td(ht,0,0);this.main_title.className='columnHeading';$td(ht,0,1).style.textAlign='right';this.tbar_div=$a($td(ht,0,1),'div','grid_tbarlinks');if(isIE)$y(this.tbar_div,{width:'200px'});this.tbar_tab=make_table(this.tbar_div,1,4,'100%',['25%','25%','25%','25%']);this.wrapper=$a(parent,'div','grid_wrapper');$h(this.wrapper,cint(screen.width*0.5)+'px');this.head_wrapper=$a(this.wrapper,'div','grid_head_wrapper');this.head_tab=$a(this.head_wrapper,'table','grid_head_table');this.head_row=this.head_tab.insertRow(0);this.tab_wrapper=$a(this.wrapper,'div','grid_tab_wrapper');this.tab=$a(this.tab_wrapper,'table','grid_table');var me=this;this.wrapper.onscroll=function(){me.head_wrapper.style.top=me.wrapper.scrollTop+'px';}}
_f.Grid.prototype.show=function(){if(this.can_add_rows){$ds(this.tbar_div);}else{$dh(this.tbar_div);}
$ds(this.wrapper);}
_f.Grid.prototype.hide=function(){$dh(this.wrapper);$dh(this.tbar_div);}
_f.Grid.prototype.insert_column=function(doctype,fieldname,fieldtype,label,width,options,perm,reqd){var idx=this.head_row.cells.length;if(!width)width='140px';if((width+'').slice(-2)!='px'){width=width+'px';}
var col=this.head_row.insertCell(idx);col.doctype=doctype;col.fieldname=fieldname;col.fieldtype=fieldtype;col.innerHTML='<div>'+label+'</div>';col.label=label;if(reqd)
col.childNodes[0].style.color="#D22";col.style.width=width;col.options=options;col.perm=perm;this.col_idx_by_name[fieldname]=idx;}
_f.Grid.prototype.reset_table_width=function(){var w=0;for(var i=0,len=this.head_row.cells.length;i<len;i++){w+=cint(this.head_row.cells[i].style.width);}
this.head_tab.style.width=w+'px';this.tab.style.width=w+'px';}
_f.Grid.prototype.set_column_disp=function(fieldname,show){var cidx=this.col_idx_by_name[fieldname];if(!cidx){msgprint('Trying to hide unknown column: '+fieldname);return;}
var disp=show?'table-cell':'none';this.head_row.cells[cidx].style.display=disp;for(var i=0,len=this.tab.rows.length;i<len;i++){var cell=this.tab.rows[i].cells[cidx];cell.style.display=disp;}
this.reset_table_width();}
_f.Grid.prototype.append_row=function(idx,docname){if(!idx)idx=this.tab.rows.length;var row=this.tab.insertRow(idx);row.docname=docname;if(idx%2)var odd=true;else var odd=false;var me=this;for(var i=0;i<this.head_row.cells.length;i++){var cell=row.insertCell(i);var hc=this.head_row.cells[i];cell.style.width=hc.style.width;cell.style.display=hc.style.display;cell.row=row;cell.grid=this;cell.className='grid_cell';cell.div=$a(cell,'div','grid_cell_div');if(this.row_height){cell.div.style.height=this.row_height;}
cell.div.cell=cell;cell.div.onclick=function(e){me.cell_click(this.cell,e);}
if(odd){$bg(cell,this.alt_row_bg);cell.is_odd=1;cell.div.style.border='2px solid '+this.alt_row_bg;}else $bg(cell,'#FFF');if(!hc.fieldname)cell.div.style.cursor='default';}
this.set_ht();return row;}
_f.Grid.prototype.refresh_cell=function(docname,fieldname){for(var r=0;r<this.tab.rows.length;r++){if(this.tab.rows[r].docname==docname){for(var c=0;c<this.head_row.cells.length;c++){var hc=this.head_row.cells[c];if(hc.fieldname==fieldname){this.set_cell_value(this.tab.rows[r].cells[c]);}}}}}
_f.cur_grid;_f.cur_grid_ridx;_f.Grid.prototype.set_cell_value=function(cell){if(cell.row.is_newrow)return;var hc=this.head_row.cells[cell.cellIndex];if(hc.fieldname){var v=locals[hc.doctype][cell.row.docname][hc.fieldname];}else{var v=(cell.row.rowIndex+1);}
if(v==null){v='';}
var me=this;if(cell.cellIndex){var ft=hc.fieldtype;if(ft=='Link'&&cur_frm.doc.docstatus<1)ft='Data';$s(cell.div,v,ft,hc.options);}else{cell.div.style.padding='2px';cell.div.style.textAlign='left';cell.innerHTML='';var t=make_table(cell,1,3,'60px',['20px','20px','20px'],{verticalAlign:'middle',padding:'2px'});$y($td(t,0,0),{paddingLeft:'4px'});$td(t,0,0).innerHTML=cell.row.rowIndex+1;if(cur_frm.editable&&this.can_edit){var ed=$a($td(t,0,1),'div','wn-icon ic-doc_edit',{cursor:'pointer'});ed.cell=cell;ed.title='Edit Row';ed.onclick=function(){_f.cur_grid=me;_f.cur_grid_ridx=this.cell.row.rowIndex;_f.edit_record(me.doctype,this.cell.row.docname,1);}}else{cell.div.innerHTML=(cell.row.rowIndex+1);cell.div.style.cursor='default';cell.div.onclick=function(){}}}}
_f.Grid.prototype.cell_click=function(cell,e){if(_f.cur_grid_cell==cell)
return;this.cell_select(cell);if(cur_frm.editable){if(isIE){window.event.cancelBubble=true;window.event.returnValue=false;}else{e.preventDefault();}}}
_f.Grid.prototype.notify_click=function(e,target){if(_f.cur_grid_cell&&!target.isactive){if(!(text_dialog&&text_dialog.display)&&!datepicker_active&&!(selector&&selector.display)&&!(cur_autosug)){_f.cur_grid_cell.grid.cell_deselect();}}}
_f.Grid.prototype.cell_deselect=function(){if(_f.cur_grid_cell){var c=_f.cur_grid_cell;c.grid.remove_template(c);c.div.className='grid_cell_div';if(c.is_odd)c.div.style.border='2px solid '+c.grid.alt_row_bg;else c.div.style.border='2px solid #FFF';_f.cur_grid_cell=null;_f.cur_grid=null;this.isactive=false;delete click_observers[this.observer_id];}}
_f.Grid.prototype.cell_select=function(cell,ri,ci){if(ri!=null&&ci!=null)
cell=this.tab.rows[ri].cells[ci];var hc=this.head_row.cells[cell.cellIndex];if(!hc.template){this.make_template(hc);}
hc.template.perm=this.field?this.field.perm:hc.perm;if(hc.fieldname&&hc.template.get_status()=='Write'){this.cell_deselect();cell.div.style.border='2px solid #88F';_f.cur_grid_cell=cell;this.add_template(cell);this.isactive=true;click_observers.push(this);this.observer_id=click_observers.length-1;}}
_f.Grid.prototype.add_template=function(cell){if(!cell.row.docname&&this.add_newrow){this.add_newrow();this.cell_select(cell);}else{var hc=this.head_row.cells[cell.cellIndex];cell.div.innerHTML='';cell.div.appendChild(hc.template.wrapper);hc.template.activate(cell.row.docname);hc.template.activated=1;if(hc.template.input&&hc.template.input.set_width){hc.template.input.set_width(isIE?cell.offsetWidth:cell.clientWidth);}}}
_f.Grid.prototype.get_field=function(fieldname){for(var i=0;i<this.head_row.cells.length;i++){var hc=this.head_row.cells[i];if(hc.fieldname==fieldname){if(!hc.template){this.make_template(hc);}
return hc.template;}}
return{}}
_f.grid_date_cell='';_f.grid_refresh_date=function(){_f.grid_date_cell.grid.set_cell_value(_f.grid_date_cell);}
_f.grid_refresh_field=function(temp,input){if(input.value!=_f.get_value(temp.doctype,temp.docname,temp.df.fieldname))
if(input.onchange)input.onchange();}
_f.Grid.prototype.remove_template=function(cell){var hc=this.head_row.cells[cell.cellIndex];if(!hc.template)return;if(!hc.template.activated)return;if(hc.template.txt){if(hc.template.df.fieldtype=='Date'){_f.grid_date_cell=cell;setTimeout('_f.grid_refresh_date()',100);}
if(hc.template.txt.value)
_f.grid_refresh_field(hc.template,hc.template.txt);}else if(hc.template.input){_f.grid_refresh_field(hc.template,hc.template.input);}
if(hc.template&&hc.template.wrapper.parentNode)
cell.div.removeChild(hc.template.wrapper);this.set_cell_value(cell);hc.template.activated=0;if(isIE6){$dh(this.wrapper);$ds(this.wrapper);}}
_f.Grid.prototype.notify_keypress=function(e,keycode){if(keycode>=37&&keycode<=40&&e.shiftKey){if(text_dialog&&text_dialog.display){return;}}else
return;if(!_f.cur_grid_cell)return;if(_f.cur_grid_cell.grid!=this)return;var ri=_f.cur_grid_cell.row.rowIndex;var ci=_f.cur_grid_cell.cellIndex;switch(keycode){case 38:if(ri>0){this.cell_select('',ri-1,ci);}break;case 40:if(ri<(this.tab.rows.length-1)){this.cell_select('',ri+1,ci);}break;case 39:if(ci<(this.head_row.cells.length-1)){this.cell_select('',ri,ci+1);}break;case 37:if(ci>1){this.cell_select('',ri,ci-1);}break;}}
_f.Grid.prototype.make_template=function(hc){hc.template=make_field(get_field(hc.doctype,hc.fieldname),hc.doctype,'',this.field.frm,true);hc.template.grid=this;}
_f.Grid.prototype.append_rows=function(n){for(var i=0;i<n;i++)this.append_row();}
_f.Grid.prototype.truncate_rows=function(n){for(var i=0;i<n;i++)this.tab.deleteRow(this.tab.rows.length-1);}
_f.Grid.prototype.set_data=function(data){this.cell_deselect();this.reset_table_width();if(data.length>this.tab.rows.length)
this.append_rows(data.length-this.tab.rows.length);if(data.length<this.tab.rows.length)
this.truncate_rows(this.tab.rows.length-data.length);for(var ridx=0;ridx<data.length;ridx++){this.refresh_row(ridx,data[ridx]);}
if(this.can_add_rows&&this.make_newrow){this.make_newrow();}
this.set_ht();if(this.wrapper.onscroll)this.wrapper.onscroll();}
_f.Grid.prototype.set_ht=function(ridx,docname){var ht=((cint(this.row_height)+10)*(((this.tab&&this.tab.rows)?this.tab.rows.length:0)+1));if(ht<100)ht=100;if(ht>cint(0.3*screen.width))ht=cint(0.3*screen.width);ht+=4;$y(this.wrapper,{height:ht+'px'});}
_f.Grid.prototype.refresh_row=function(ridx,docname){var row=this.tab.rows[ridx];row.docname=docname;row.is_newrow=false;for(var cidx=0;cidx<row.cells.length;cidx++){this.set_cell_value(row.cells[cidx]);}}
_f.FormGrid=function(field){this.field=field;this.doctype=field.df.options;if(!this.doctype){show_alert('No Options for table '+field.df.label);}
this.col_break_width=cint(this.field.col_break_width);if(!this.col_break_width)this.col_break_width=100;$y(field.parent,{marginTop:'8px'});this.init(field.parent,field.df.width);this.setup();}
_f.FormGrid.prototype=new _f.Grid();_f.FormGrid.prototype.setup=function(){this.make_columns();}
_f.FormGrid.prototype.make_tbar_link=function(parent,label,fn,icon){var div=$a(parent,'div','',{cursor:'pointer'});var t=make_table(div,1,2,'90%',['20px',null]);var img=$a($td(t,0,0),'div','wn-icon '+icon);$y($td(t,0,0),{textAlign:'right'});var l=$a($td(t,0,1),'span','link_type',{color:'#333'});l.style.fontSize='11px';l.innerHTML=label;div.onclick=fn;div.show=function(){$ds(this);}
div.hide=function(){$dh(this);}
$td(t,0,0).isactive=1;$td(t,0,1).isactive=1;l.isactive=1;div.isactive=1;img.isactive=1;return div;}
_f.FormGrid.prototype.make_buttons=function(){var me=this;this.tbar_btns={};this.tbar_btns['Del']=this.make_tbar_link($td(this.tbar_tab,0,0),'Del',function(){me.delete_row();},'ic-round_minus');this.tbar_btns['Ins']=this.make_tbar_link($td(this.tbar_tab,0,1),'Ins',function(){me.insert_row();},'ic-round_plus');this.tbar_btns['Up']=this.make_tbar_link($td(this.tbar_tab,0,2),'Up',function(){me.move_row(true);},'ic-arrow_top');this.tbar_btns['Dn']=this.make_tbar_link($td(this.tbar_tab,0,3),'Dn',function(){me.move_row(false);},'ic-arrow_bottom');for(var i in this.btns)
this.btns[i].isactive=true;}
_f.FormGrid.prototype.make_columns=function(){var gl=fields_list[this.field.df.options];if(!gl){alert('Table details not found "'+this.field.df.options+'"');}
gl.sort(function(a,b){return a.idx-b.idx});var p=this.field.perm;for(var i=0;i<gl.length;i++){if(p[this.field.df.permlevel]&&p[this.field.df.permlevel][READ]){this.insert_column(this.field.df.options,gl[i].fieldname,gl[i].fieldtype,gl[i].label,gl[i].width,gl[i].options,this.field.perm,gl[i].reqd);if(gl[i].hidden){this.set_column_disp(gl[i].fieldname,false);}}}}
_f.FormGrid.prototype.set_column_label=function(fieldname,label){for(var i=0;i<this.head_row.cells.length;i++){var c=this.head_row.cells[i];if(c.fieldname==fieldname){c.innerHTML='<div class="grid_head_div">'+label+'</div>';c.cur_label=label;break;}}}
_f.FormGrid.prototype.refresh=function(){var docset=getchildren(this.doctype,this.field.frm.docname,this.field.df.fieldname,this.field.frm.doctype);var data=[];for(var i=0;i<docset.length;i++){locals[this.doctype][docset[i].name].idx=i+1;data[data.length]=docset[i].name;}
this.set_data(data);}
_f.FormGrid.prototype.set_unsaved=function(){locals[cur_frm.doctype][cur_frm.docname].__unsaved=1;cur_frm.set_heading();}
_f.FormGrid.prototype.insert_row=function(){var d=this.new_row_doc();var ci=_f.cur_grid_cell.cellIndex;var row_idx=_f.cur_grid_cell.row.rowIndex;d.idx=row_idx+1;for(var ri=row_idx;ri<this.tab.rows.length;ri++){var r=this.tab.rows[ri];if(r.docname)
locals[this.doctype][r.docname].idx++;}
this.refresh();this.cell_select('',row_idx,ci);this.set_unsaved();}
_f.FormGrid.prototype.new_row_doc=function(){var n=LocalDB.create(this.doctype);var d=locals[this.doctype][n];d.parent=this.field.frm.docname;d.parentfield=this.field.df.fieldname;d.parenttype=this.field.frm.doctype;return d;}
_f.FormGrid.prototype.add_newrow=function(){var r=this.tab.rows[this.tab.rows.length-1];if(!r.is_newrow)
show_alert('fn: add_newrow: Adding a row which is not flagged as new');var d=this.new_row_doc();d.idx=r.rowIndex+1;r.docname=d.name;r.is_newrow=false;this.set_cell_value(r.cells[0]);this.make_newrow();this.refresh_row(r.rowIndex,d.name);if(this.onrowadd)this.onrowadd(cur_frm.doc,d.doctype,d.name);return d.name;}
_f.FormGrid.prototype.make_newrow=function(from_add_btn){if(!this.can_add_rows)
return;if(this.tab.rows.length){var r=this.tab.rows[this.tab.rows.length-1];if(r.is_newrow)
return;}
var r=this.append_row();r.cells[0].div.innerHTML='<b style="font-size: 18px;">*</b>';r.is_newrow=true;}
_f.FormGrid.prototype.check_selected=function(){if(!_f.cur_grid_cell){show_alert('Select a cell first');return false;}
if(_f.cur_grid_cell.grid!=this){show_alert('Select a cell first');return false;}
return true;}
_f.FormGrid.prototype.delete_row=function(dt,dn){if(dt&&dn){LocalDB.delete_record(dt,dn);this.refresh();}else{if(!this.check_selected())return;var r=_f.cur_grid_cell.row;if(r.is_newrow)return;var ci=_f.cur_grid_cell.cellIndex;var ri=_f.cur_grid_cell.row.rowIndex;LocalDB.delete_record(this.doctype,r.docname);this.refresh();if(ri<(this.tab.rows.length-2))
this.cell_select(null,ri,ci);else _f.cur_grid_cell=null;}
this.set_unsaved();}
_f.FormGrid.prototype.move_row=function(up){if(!this.check_selected())return;var r=_f.cur_grid_cell.row;if(r.is_newrow)return;if(up&&r.rowIndex>0){var swap_row=this.tab.rows[r.rowIndex-1];}else if(!up){var len=this.tab.rows.length;if(this.tab.rows[len-1].is_newrow)
len=len-1;if(r.rowIndex<(len-1))
var swap_row=this.tab.rows[r.rowIndex+1];}
if(swap_row){var cidx=_f.cur_grid_cell.cellIndex;this.cell_deselect();var aidx=locals[this.doctype][r.docname].idx;locals[this.doctype][r.docname].idx=locals[this.doctype][swap_row.docname].idx;locals[this.doctype][swap_row.docname].idx=aidx;var adocname=swap_row.docname;this.refresh_row(swap_row.rowIndex,r.docname);this.refresh_row(r.rowIndex,adocname);this.cell_select(this.tab.rows[swap_row.rowIndex].cells[cidx]);this.set_unsaved();}}
_p.show_dialog=function(){if(!_p.dialog){_p.make_dialog();}
_p.dialog.show();}
_p.make_dialog=function(){var d=new Dialog(360,140,"Print Formats");d.make_body([['HTML','Select'],['Check','No Letterhead','Will ignore letterhead if it can be set. May not work for all formats'],['HTML','Buttons']]);d.widgets['No Letterhead'].checked=1;$btn(d.widgets.Buttons,'Print',function(){_p.build(sel_val(cur_frm.print_sel),_p.go,d.widgets['No Letterhead'].checked);},{cssFloat:'right',marginBottom:'16px',marginLeft:'7px'},'green');$btn(d.widgets.Buttons,'Preview',function(){_p.build(sel_val(cur_frm.print_sel),_p.preview,d.widgets['No Letterhead'].checked);},{cssFloat:'right',marginBottom:'16px'},'');_p.dialog=d;d.onshow=function(){var c=d.widgets['Select'];if(c.cur_sel&&c.cur_sel.parentNode==c)
c.removeChild(c.cur_sel);c.appendChild(cur_frm.print_sel);c.cur_sel=cur_frm.print_sel;}}
_p.field_tab=function(layout_cell){var t=$a(layout_cell,'table','',{width:'100%'});var r=t.insertRow(0);this.r=r;r.insertCell(0);r.insertCell(1);r.cells[0].className='datalabelcell';r.cells[1].className='datainputcell';return r}
_p.print_std_add_table=function(t,layout,pf_list,dt,no_letterhead){if(t.appendChild){layout.cur_cell.appendChild(t);}else{for(var ti=0;ti<t.length-1;ti++){layout.cur_cell.appendChild(t[ti]);layout.close_borders();pf_list[pf_list.length]='<div style="page-break-after: always;" class="page_break"></div>';layout=_p.add_layout(dt,no_letterhead);pf_list[pf_list.length]=layout;layout.addrow();layout.addcell();var div=$a(layout.cur_cell,'div');div.innerHTML='Continued from previous page...';div.style.padding='4px';}
layout.cur_cell.appendChild(t[t.length-1]);}
return layout;}
_p.print_std_add_field=function(dt,dn,f,layout){var v=_f.get_value(dt,dn,f.fieldname);if(f.fieldtype!="Button"){if(!v&&!in_list(['Float','Int','Currency'],f.fieldtype)){}else{r=_p.field_tab(layout.cur_cell)
r.cells[0].innerHTML=f.label?f.label:f.fieldname;$s(r.cells[1],v,f.fieldtype);if(f.fieldtype=='Currency')
$y(r.cells[1],{textAlign:'left'});}}}
_p.get_letter_head=function(){var cp=locals['Control Panel']['Control Panel'];if(cur_frm.doc.letter_head)
var lh=cstr(_p.letter_heads[cur_frm.doc.letter_head]);else if(cp.letter_head)
var lh=cp.letter_head;else
var lh='';return lh;}
_p.add_layout=function(dt,no_letterhead){var l=new Layout();l.addrow();if(locals['DocType'][dt].print_outline=='Yes')l.with_border=1;return l;}
_p.print_std=function(no_letterhead){var dn=cur_frm.docname;var dt=cur_frm.doctype;var pf_list=[];var layout=_p.add_layout(dt,no_letterhead);pf_list[pf_list.length]=layout;var h1=$a(layout.cur_row.header,'h1','',{fontSize:'22px',marginBottom:'8px'});h1.innerHTML=cur_frm.pformat[dn]?cur_frm.pformat[dn]:get_doctype_label(dt);var h2=$a(layout.cur_row.header,'div','',{fontSize:'16px',color:'#888',marginBottom:'8px',paddingBottom:'8px',borderBottom:(layout.with_border?'0px':'1px solid #000')});h2.innerHTML=dn;var fl=getchildren('DocField',dt,'fields','DocType');if(fl[0]&&fl[0].fieldtype!="Section Break"){layout.addrow();if(fl[0].fieldtype!="Column Break")
layout.addcell();}
for(var i=0;i<fl.length;i++){var fn=fl[i].fieldname?fl[i].fieldname:fl[i].label;if(fn)
var f=get_field(dt,fn,dn);else
var f=fl[i];if(!f.print_hide){if(cur_frm.pformat[f.fieldname]){var tmp=$a(layout.cur_cell,'div');tmp.innerHTML=cur_frm.pformat[f.fieldname](locals[dt][dn]);}else{switch(f.fieldtype){case'Section Break':layout.addrow();if(fl[i+1]&&(fl[i+1].fieldtype!='Column Break')){layout.addcell();}
break;case'Column Break':layout.addcell(f.width,f.label);break;case'Table':var t=print_table(dt,dn,f.fieldname,f.options,null,null,null,null);layout=_p.print_std_add_table(t,layout,pf_list,dt,no_letterhead);break;case'HTML':var tmp=$a(layout.cur_cell,'div');tmp.innerHTML=f.options;break;case'Code':var tmp=$a(layout.cur_cell,'div');var v=_f.get_value(dt,dn,f.fieldname);tmp.innerHTML='<div>'+f.label+': </div>'+'<pre style="font-family: Courier, Fixed;">'+(v?v:'')+'</pre>';break;case'Text Editor':var tmp=$a(layout.cur_cell,'div');var v=_f.get_value(dt,dn,f.fieldname);tmp.innerHTML=v?v:'';break;default:_p.print_std_add_field(dt,dn,f,layout);}}}}
layout.close_borders();var html='';for(var i=0;i<pf_list.length;i++){if(pf_list[i].wrapper){html+=pf_list[i].wrapper.innerHTML;}else if(pf_list[i].innerHTML){html+=pf_list[i].innerHTML;}else{html+=pf_list[i];}}
pf_list=[];return html;}
_p.print_style=".datalabelcell {padding: 2px 0px; width: 38%;vertical-align:top; }"
+".datainputcell { padding: 2px 0px; width: 62%; text-align:left; }"
+".sectionHeading { font-size: 16px; font-weight: bold; margin: 8px 0px }"
+".columnHeading { font-size: 14px; font-weight: bold; margin: 8px 0px; }"
_p.formats={}
_p.build=function(fmtname,onload,no_letterhead,only_body){if(!cur_frm){alert('No Document Selected');return;}
var doc=locals[cur_frm.doctype][cur_frm.docname];if(fmtname=='Standard'){onload(_p.render(_p.print_std(no_letterhead),_p.print_style,doc,doc.name,no_letterhead,only_body));}else{if(!_p.formats[fmtname])
$c('webnotes.widgets.form.get_print_format',{'name':fmtname},function(r,rt){_p.formats[fmtname]=r.message;onload(_p.render(_p.formats[fmtname],'',doc,doc.name,no_letterhead,only_body));});else
onload(_p.render(_p.formats[fmtname],'',doc,doc.name,no_letterhead,only_body));}}
_p.render=function(body,style,doc,title,no_letterhead,only_body){var block=document.createElement('div');var tmp_html='';if(doc&&cint(doc.docstatus)==0&&cur_frm.perm[0][SUBMIT]){var tmp_html='<div style="text-align: center; padding: 8px; background-color: #CCC; "><div style="font-size: 20px; font-weight: bold; ">DRAFT</div>This box will go away after the document is submitted.</div>';}
if(doc&&doc.__archived){var tmp_html='<div style="text-align: center; padding: 8px; background-color: #CCC; "><div style="font-size: 20px; font-weight: bold; ">ARCHIVED</div>You must restore this document to make it editable.</div>';}
style=(only_body?'':_p.def_print_style_body)+_p.def_print_style_other+style;block.innerHTML=body;var jslist=block.getElementsByTagName('script');while(jslist.length>0){for(var i=0;i<jslist.length;i++){var code=jslist[i].innerHTML;var p=jslist[i].parentNode;var sp=$a(p,'span');p.replaceChild(sp,jslist[i]);var h=eval(code);if(!h)h='';sp.innerHTML=h;}
jslist=block.getElementsByTagName('script');}
if(only_body)
show_lh=false;else{if(!no_letterhead)show_lh=true;else show_lh=false;}
if(show_lh){block.innerHTML='<div>'+_p.get_letter_head()+'</div>'+block.innerHTML;}
if(only_body){return tmp_html+block.innerHTML.replace(/<td/g,'\n<td').replace(/<div/g,'\n<div');}else{return'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">\n'
+'<html><head>'
+'<title>'+title+'</title>'
+'<style>'+style+'</style>'
+'</head><body>'
+tmp_html
+block.innerHTML.replace(/<td/g,'\n<td')
+'</body></html>';}}
print_table=function(dt,dn,fieldname,tabletype,cols,head_labels,widths,condition,cssClass){var fl=fields_list[tabletype];var ds=getchildren(tabletype,dn,fieldname,dt);var tl=[];var cell_style={border:'1px solid #000',padding:'2px',verticalAlign:'top'};var head_cell_style={border:'1px solid #000',padding:'2px',verticalAlign:'top',backgroundColor:'#ddd'};var make_table=function(fl){var w=document.createElement('div');var t=$a(w,'table','',{width:'100%',borderCollapse:'collapse',marginBottom:'10px'});t.wrapper=w;t.insertRow(0);var c_start=0;if(fl[0]=='SR'){var cell=t.rows[0].insertCell(0)
cell.innerHTML=head_labels?head_labels[0]:'<b>Sr</b>';$y(cell,{width:'30px'});$y(cell,head_cell_style)
c_start=1;}
for(var c=c_start;c<fl.length;c++){var cell=t.rows[0].insertCell(c);$y(cell,head_cell_style)
if(head_labels)
cell.innerHTML=head_labels[c];else
cell.innerHTML=fl[c].label;if(fl[c].width)
$y(cell,{width:fl[c].width});if(widths)
$y(cell,{width:widths[c]});if(fl[c].fieldtype=='Currency')
$y(cell,{textAlign:'right'});cell.style.fontWeight='bold';}
return t;}
if(!ds.length)return document.createElement('div');var newfl=[];if(cols&&cols.length){if(cols[0]=='SR')newfl[0]='SR';for(var i=0;i<cols.length;i++){for(var j=0;j<fl.length;j++){if(fl[j].fieldname==cols[i]){newfl[newfl.length]=fl[j];break;}}}}else{newfl=['SR']
for(var j=0;j<fl.length;j++){if(!fl[j].print_hide){newfl[newfl.length]=fl[j];}}}
fl=newfl;var t=make_table(fl);tl.push(t.wrapper);var c_start=0;if(fl[0]=='SR'){c_start=1;}
var sr=0;for(var r=0;r<ds.length;r++){if((!condition)||(condition(ds[r]))){if(ds[r].page_break){var t=make_table(fl);tl.push(t.wrapper);}
var rowidx=t.rows.length;sr++
var row=t.insertRow(rowidx);if(c_start){var cell=row.insertCell(0);cell.innerHTML=sr;$y(cell,cell_style);}
for(var c=c_start;c<fl.length;c++){var cell=row.insertCell(c);$y(cell,cell_style);$s(cell,ds[r][fl[c].fieldname],fl[c].fieldtype);if(fl[c].fieldtype=='Currency')
cell.style.textAlign='right';}}}
if(tl.length>1)return tl;else return tl[0];}
_e.email_as_field='email_id';_e.email_as_dt='Contact';_e.email_as_in='email_id,contact_name';sendmail=function(emailto,emailfrom,cc,subject,message,fmt,with_attachments){var fn=function(html){$c('webnotes.utils.email_lib.send_form',{'sendto':emailto,'sendfrom':emailfrom?emailfrom:'','cc':cc?cc:'','subject':subject,'message':replace_newlines(message),'body':html,'full_domain':wn.urllib.get_base_url(),'with_attachments':with_attachments?1:0,'dt':cur_frm.doctype,'dn':cur_frm.docname},function(r,rtxt){});}
_p.build(fmt,fn);}
_e.make=function(){var d=new Dialog(440,440,"Send Email");var email_go=function(){var emailfrom=d.widgets['From'].value;var emailto=d.widgets['To'].value;if(!emailfrom)
emailfrom=user_email;var email_list=emailto.split(/[,|;]/);var valid=1;for(var i=0;i<email_list.length;i++){if(!validate_email(email_list[i])){msgprint('error:'+email_list[i]+' is not a valid email id');valid=0;}}
if(emailfrom&&!validate_email(emailfrom)){msgprint('error:'+emailfrom+' is not a valid email id. To change the default please click on Profile on the top right of the screen and change it.');return;}
if(!valid)return;var cc=emailfrom;if(!emailfrom){emailfrom=locals['Control Panel']['Control Panel'].auto_email_id;cc='';}
sendmail(emailto,emailfrom,emailfrom,d.widgets['Subject'].value,d.widgets['Message'].value,sel_val(cur_frm.print_sel),d.widgets['Send With Attachments'].checked);_e.dialog.hide();}
d.onhide=function(){hide_autosuggest();}
d.make_body([['Data','To','Example: abc@hotmail.com, xyz@yahoo.com'],['Select','Format'],['Data','Subject'],['Data','From','Optional'],['Check','Send With Attachments','Will send all attached documents (if any)'],['Text','Message'],['Button','Send',email_go]]);d.widgets['From'].value=(user_email?user_email:'');$td(d.rows['Format'].tab,0,1).cur_sel=d.widgets['Format'];var opts={script:'',json:true,maxresults:10};var as=new AutoSuggest(d.widgets['To'],opts);as.custom_select=function(txt,sel){var r='';var tl=txt.split(',');for(var i=0;i<tl.length-1;i++)r=r+tl[i]+',';r=r+(r?' ':'')+sel;if(r[r.length-1]==NEWLINE)r=substr(0,r.length-1);return r;}
var emailto=d.widgets['To']
as.set_input_value=function(new_txt){if(emailto.value&&emailto.value.indexOf(',')!=-1){var txt=emailto.value.split(',');txt.splice(txt.length-1,1,new_txt);for(var i=0;i<txt.length-1;i++)txt[i]=strip(txt[i]);emailto.value=txt.join(', ');}else{emailto.value=new_txt;}}
as.doAjaxRequest=function(txt){var pointer=as;var q='';var last_txt=txt.split(',');last_txt=last_txt[last_txt.length-1];var call_back=function(r,rt){as.aSug=[];if(!r.cl)return;for(var i=0;i<r.cl.length;i++){as.aSug.push({'id':r.cl[i],'value':r.cl[i],'info':''});}
as.createList(as.aSug);}
$c('webnotes.utils.email_lib.get_contact_list',{'select':_e.email_as_field,'from':_e.email_as_dt,'where':_e.email_as_in,'txt':(last_txt?strip(last_txt):'%')},call_back);return;}
var sel;_e.dialog=d;}
$c_get_values=function(args,doc,dt,dn,user_callback){var call_back=function(r,rt){if(!r.message)return;if(user_callback)user_callback(r.message);var fl=args.fields.split(',');for(var i in fl){locals[dt][dn][fl[i]]=r.message[fl[i]];if(args.table_field)
refresh_field(fl[i],dn,args.table_field);else
refresh_field(fl[i]);}}
$c('webnotes.widgets.form.get_fields',args,call_back);}
get_server_fields=function(method,arg,table_field,doc,dt,dn,allow_edit,call_back){if(!allow_edit)freeze('Fetching Data...');$c('runserverobj',args={'method':method,'docs':compress_doclist([doc]),'arg':arg},function(r,rt){if(r.message){var d=locals[dt][dn];var field_dict=r.message;for(var key in field_dict){d[key]=field_dict[key];if(table_field)refresh_field(key,d.name,table_field);else refresh_field(key);}}
if(call_back){doc=locals[doc.doctype][doc.name];call_back(doc,dt,dn);}
if(!allow_edit)unfreeze();});}
set_multiple=function(dt,dn,dict,table_field){var d=locals[dt][dn];for(var key in dict){d[key]=dict[key];if(table_field)refresh_field(key,d.name,table_field);else refresh_field(key);}}
refresh_many=function(flist,dn,table_field){for(var i in flist){if(table_field)refresh_field(flist[i],dn,table_field);else refresh_field(flist[i]);}}
set_field_tip=function(n,txt){var df=get_field(cur_frm.doctype,n,cur_frm.docname);if(df)df.description=txt;if(cur_frm&&cur_frm.fields_dict){if(cur_frm.fields_dict[n])
cur_frm.fields_dict[n].comment_area.innerHTML=replace_newlines(txt);else
errprint('[set_field_tip] Unable to set field tip: '+n);}}
refresh_field=function(n,docname,table_field){if(typeof n==typeof[])refresh_many(n,docname,table_field);if(table_field){if(_f.frm_dialog&&_f.frm_dialog.display){if(_f.frm_dialog.cur_frm.fields_dict[n]&&_f.frm_dialog.cur_frm.fields_dict[n].refresh)
_f.frm_dialog.cur_frm.fields_dict[n].refresh();}else{var g=_f.cur_grid_cell;if(g)var hc=g.grid.head_row.cells[g.cellIndex];if(g&&hc&&hc.fieldname==n&&g.row.docname==docname){hc.template.refresh();}else{cur_frm.fields_dict[table_field].grid.refresh_cell(docname,n);}}}else if(cur_frm&&cur_frm.fields_dict){if(cur_frm.fields_dict[n]&&cur_frm.fields_dict[n].refresh)
cur_frm.fields_dict[n].refresh();}}
set_field_options=function(n,txt){var df=get_field(cur_frm.doctype,n,cur_frm.docname);if(df)df.options=txt;refresh_field(n);}
set_field_permlevel=function(n,level){var df=get_field(cur_frm.doctype,n,cur_frm.docname);if(df)df.permlevel=level;refresh_field(n);}
hide_field=function(n){function _hide_field(n,hidden){var df=get_field(cur_frm.doctype,n,cur_frm.docname);if(df)df.hidden=hidden;refresh_field(n);}
if(cur_frm){if(n.substr)_hide_field(n,1);else{for(var i in n)_hide_field(n[i],1)}}}
unhide_field=function(n){function _hide_field(n,hidden){var df=get_field(cur_frm.doctype,n,cur_frm.docname);if(df)df.hidden=hidden;refresh_field(n);}
if(cur_frm){if(n.substr)_hide_field(n,0);else{for(var i in n)_hide_field(n[i],0)}}}
get_field_obj=function(fn){return cur_frm.fields_dict[fn];}
wn.widgets.form.comments={n_comments:{},comment_list:{},sync:function(dt,dn,r){var f=wn.widgets.form.comments;f.n_comments[dn]=r.n_comments;f.comment_list[dn]=r.comment_list;},add:function(input,dt,dn,callback){$c('webnotes.widgets.form.add_comment',wn.widgets.form.comments.get_args(input,dt,dn),function(r,rt){wn.widgets.form.comments.update_comment_list(input,dt,dn);input.value='';callback(input,dt,dn);});},remove:function(dt,dn,comment_id,callback){$c('webnotes.widgets.form.remove_comment',{id:comment_id,dt:dt,dn:dn},callback);},get_args:function(input,dt,dn){return{comment:input.value,comment_by:user,comment_by_fullname:user_fullname,comment_doctype:dt,comment_docname:dn}},update_comment_list:function(input,dt,dn){var f=wn.widgets.form.comments;f.n_comments[dn]=cint(f.n_comments[dn])+1;f.comment_list[dn]=add_lists([f.get_args(input,dt,dn)],f.comment_list[dn]);}}
CommentList=function(parent,dt,dn){this.wrapper=$a(parent,'div','',{margin:'16px'});this.input_area=$a(this.wrapper,'div','',{margin:'2px'});this.lst_area=$a(this.wrapper,'div','',{margin:'2px'});this.make_input();this.make_lst();this.dt;this.dn;}
CommentList.prototype.run=function(){this.lst.run();}
CommentList.prototype.make_input=function(){var me=this;this.input=$a(this.input_area,'textarea','',{height:'60px',width:'300px',fontSize:'14px'});this.btn=$btn($a(this.input_area,'div'),'Post',function(){me.add_comment();},{marginTop:'8px'});}
CommentList.prototype.add_comment=function(){var me=this;var callback=function(input,dt,dn){me.lst.run();}
wn.widgets.form.comments.add(this.input,cur_frm.docname,cur_frm.doctype,callback)}
CommentList.prototype.make_lst=function(){if(!this.lst){var l=new Listing('Comments',1);var me=this;l.colwidths=['100%'];l.opts.hide_export=1;l.opts.hide_print=1;l.opts.hide_refresh=1;l.opts.no_border=1;l.opts.hide_rec_label=0;l.opts.show_calc=0;l.opts.round_corners=0;l.opts.alt_cell_style={};l.opts.cell_style={padding:'3px'};l.no_rec_message='No comments yet. Be the first one to comment!';l.get_query=function(){this.query=repl("select t1.name, t1.comment, t1.comment_by, '', t1.creation, t1.comment_doctype, t1.comment_docname, ifnull(concat_ws(' ',ifnull(t2.first_name,''),ifnull(t2.middle_name,''),ifnull(t2.last_name,'')),''), '', DAYOFMONTH(t1.creation), MONTHNAME(t1.creation), YEAR(t1.creation), hour(t1.creation), minute(t1.creation), second(t1.creation) from `tabComment Widget Record` t1, `tabProfile` t2 where t1.comment_doctype = '%(dt)s' and t1.comment_docname = '%(dn)s' and t1.comment_by = t2.name order by t1.creation desc",{dt:me.dt,dn:me.dn});this.query_max=repl("select count(name) from `tabComment Widget Record` where comment_doctype='%(dt)s' and comment_docname='%(dn)s'",{'dt':me.dt,'dn':me.dn});}
l.show_cell=function(cell,ri,ci,d){new CommentItem(cell,ri,ci,d,me)}
this.lst=l;this.lst.make(this.lst_area);}}
CommentItem=function(cell,ri,ci,d,comment){this.comment=comment;$y(cell,{padding:'4px 0px'})
var t=make_table(cell,1,3,'100%',['15%','65%','20%'],{padding:'4px'});this.img=$a($td(t,0,0),'img','',{width:'40px'});this.cmt_by=$a($td(t,0,0),'div');this.set_picture(d,ri);this.cmt_dtl=$a($td(t,0,1),'div','comment',{fontSize:'11px'});this.cmt=$a($td(t,0,1),'div','',{fontSize:'14px'});this.show_cmt($td(t,0,1),ri,ci,d);this.cmt_delete($td(t,0,2),ri,ci,d);}
CommentItem.prototype.set_picture=function(d,ri){set_user_img(this.img,user)
this.cmt_by.innerHTML=d[ri][7]?d[ri][7]:d[ri][2];}
CommentItem.prototype.show_cmt=function(cell,ri,ci,d){if(d[ri][4]){hr=d[ri][12];min=d[ri][13];sec=d[ri][14];if(parseInt(hr)>12){time=(parseInt(hr)-12)+':'+min+' PM'}
else{time=hr+':'+min+' AM'}}
this.cmt_dtl.innerHTML='On '+d[ri][10].substring(0,3)+' '+d[ri][9]+', '+d[ri][11]+' at '+time;this.cmt.innerHTML=replace_newlines(d[ri][1]);}
CommentItem.prototype.cmt_delete=function(cell,ri,ci,d){var me=this;if(d[ri][2]==user||d[ri][3]==user){del=$a(cell,'div','wn-icon ic-trash',{cursor:'pointer'});del.cmt_id=d[ri][0];del.onclick=function(){wn.widgets.form.comments.remove(cur_frm.doctype,cur_frm.docname,this.cmt_id,function(){me.comment.lst.run();})}}}
wn.widgets.form.sidebar={Sidebar:function(form){var me=this;this.form=form;this.opts={sections:[{title:'Actions',items:[{type:'link',label:'New',icon:'ic-doc_new',display:function(){return in_list(profile.can_create,form.doctype)},onclick:function(){new_doc(me.form.doctype)}},{type:'link',label:'Refresh',icon:'ic-playback_reload',onclick:function(){me.form.reload_doc()}},{type:'link',label:'Print',display:function(){return!me.form.doc.__islocal},icon:'ic-print',onclick:function(){me.form.print_doc()}},{type:'link',label:'Email',display:function(){return!me.form.doc.__islocal},icon:'ic-mail',onclick:function(){me.form.email_doc()}},{type:'link',label:'Copy',display:function(){return in_list(profile.can_create,me.form.doctype)&&!me.form.meta.allow_copy},icon:'ic-clipboard_copy',onclick:function(){me.form.copy_doc()}},{type:'link',label:'Delete',display:function(){return me.form.meta.allow_trash&&cint(me.form.doc.docstatus)!=2&&(!me.form.doc.__islocal)&&me.form.perm[0][CANCEL]},icon:'ic-trash',onclick:function(){me.form.savetrash()}}]},{title:'Attachments',render:function(wrapper){me.form.attachments=new wn.widgets.form.sidebar.Attachments(wrapper,me,me.form.doctype,me.form.docname);},display:function(){return me.form.meta.allow_attach}},{title:'Tags',render:function(wrapper){me.form.taglist=new TagList(wrapper,me.form.doc._user_tags?me.form.doc._user_tags.split(','):[],me.form.doctype,me.form.docname,0,function(){});},display:function(){return!me.form.doc.__islocal}},{title:'Comments',render:function(wrapper){new wn.widgets.form.sidebar.Comments(wrapper,me,me.form.doctype,me.form.docname);},display:function(){return!me.form.doc.__islocal}}]}
this.refresh=function(){var parent=this.form.page_layout.sidebar_area;if(!this.sidebar){$y(parent,{paddingTop:'37px'})
this.sidebar=new wn.widgets.PageSidebar(parent,this.opts);}else{this.sidebar.refresh();}}}}
wn.widgets.form.sidebar.Comments=function(parent,sidebar,doctype,docname){var me=this;this.sidebar=sidebar;this.doctype=doctype;this.docname=docname;this.refresh=function(){$c('webnotes.widgets.form.get_comments',{dt:me.doctype,dn:me.docname,limit:5},function(r,rt){wn.widgets.form.comments.sync(me.doctype,me.docname,r);me.make_body();});}
this.make_body=function(){if(this.wrapper)this.wrapper.innerHTML='';else this.wrapper=$a(parent,'div','sidebar-comment-wrapper');this.input=$a_input(this.wrapper,'text');this.btn=$btn(this.wrapper,'Post',function(){me.add_comment()},{marginLeft:'8px'});this.render_comments()}
this.render_comments=function(){var f=wn.widgets.form.comments;var cl=f.comment_list[me.docname]
this.msg=$a(this.wrapper,'div','sidebar-comment-message');if(cl){this.msg.innerHTML=cl.length+' out of '+f.n_comments[me.docname]+' comments';if(f.n_comments[me.docname]>cl.length){this.msg.innerHTML+=' <span class="link_type" onclick="cur_frm.show_comments()">Show all</span>'}
for(var i=0;i<cl.length;i++){this.render_one_comment(cl[i]);}}else{this.msg.innerHTML='Be the first one to comment.'}}
this.render_one_comment=function(det){$a(this.wrapper,'div','social sidebar-comment-text','',det.comment);$a(this.wrapper,'div','sidebar-comment-info','',comment_when(det.creation)+' by '+det.comment_by_fullname);}
this.add_comment=function(){if(!this.input.value)return;this.btn.set_working();wn.widgets.form.comments.add(this.input,me.doctype,me.docname,function(){me.btn.done_working();me.make_body();});}
this.refresh();}
wn.widgets.form.sidebar.Attachments=function(parent,sidebar,doctype,docname){var me=this;this.frm=sidebar.form;this.make=function(){if(this.wrapper)this.wrapper.innerHTML='';else this.wrapper=$a(parent,'div','sidebar-comment-wrapper');this.attach_wrapper=$a(this.wrapper,'div');if(this.frm.doc.__islocal){this.attach_wrapper.innerHTML='Attachments can be uploaded after saving'
return;}
var n=this.frm.doc.file_list?this.frm.doc.file_list.split('\n').length:0;if(n<this.frm.meta.max_attachments||!this.frm.meta.max_attachments){this.btn=$btn($a(this.wrapper,'div','sidebar-comment-message'),'Add',function(){me.add_attachment()});}
this.render();}
this.render=function(){this.attach_wrapper.innerHTML=''
var doc=locals[me.frm.doctype][me.frm.docname];var fl=doc.file_list?doc.file_list.split('\n'):[];for(var i=0;i<fl.length;i++){new wn.widgets.form.sidebar.Attachment(this.attach_wrapper,fl[i],me.frm)}}
this.add_attachment=function(){if(!this.dialog){this.dialog=new wn.widgets.Dialog({title:'Add Attachment',width:400})
$y(this.dialog.body,{margin:'13px'})
this.dialog.make();}
this.dialog.body.innerHTML='';this.dialog.show();this.uploader=new Uploader(this.dialog.body,{from_form:1,doctype:doctype,docname:docname,at_id:this.at_id},wn.widgets.form.file_upload_done);}
this.make();}
wn.widgets.form.sidebar.Attachment=function(parent,filedet,frm){filedet=filedet.split(',')
this.filename=filedet[0];this.fileid=filedet[1];this.frm=frm;var me=this;this.wrapper=$a(parent,'div','sidebar-comment-message');this.remove_fileid=function(){var doc=locals[me.frm.doctype][me.frm.docname];var fl=doc.file_list.split('\n');new_fl=[];for(var i=0;i<fl.length;i++){if(fl[i].split(',')[1]!=me.fileid)new_fl.push(fl[i]);}
doc.file_list=new_fl.join('\n');}
this.ln=$a(this.wrapper,'a','link_type',{fontSize:'11px'},this.filename);this.ln.href=outUrl+'?cmd=get_file&fname='+this.fileid;this.ln.target='_blank';this.del=$a(this.wrapper,'span','link_type',{marginLeft:'3px'},'[x]');this.del.onclick=function(){var yn=confirm("Are you sure you want to delete the attachment?")
if(yn){var callback=function(r,rt){locals[me.frm.doctype][me.frm.docname].modified=r.message;$dh(me.wrapper);me.remove_fileid();frm.refresh();}
$c('webnotes.widgets.form.remove_attach',args={'fid':me.fileid,dt:me.frm.doctype,dn:me.frm.docname},callback);}}}
wn.widgets.form.file_upload_done=function(doctype,docname,fileid,filename,at_id,new_timestamp){var at_id=cint(at_id);var doc=locals[doctype][docname];if(doc.file_list){var fl=doc.file_list.split('\n')
fl.push(filename+','+fileid)
doc.file_list=fl.join('\n');}
else
doc.file_list=filename+','+fileid;doc.modified=new_timestamp;var frm=frms[doctype];frm.attachments.dialog.hide();msgprint('File Uploaded Sucessfully.');frm.refresh();}