
/*
 *	lib/js/legacy/globals.js
 */
wn.provide('wn.widgets.form');wn.provide('wn.widgets.report');wn.provide('wn.utils');wn.provide('wn.model');wn.provide('wn.profile');wn.provide('wn.session');wn.provide('_f');wn.provide('_p');wn.provide('_r');wn.provide('_c');wn.provide('_e');wn.provide('_startup_data')
wn.settings.no_history=1;var NEWLINE='\n';var login_file='';var version='v170';var profile=null;var session={};var is_testing=false;var user=null;var user_defaults=null;var user_roles=null;var user_fullname=null;var user_email=null;var user_img={};var home_page=null;var hide_autosuggest=null;var page_body=null;var pscript={};var selector=null;var keypress_observers=[];var click_observers=[];var top_index=91;var _f={};var _p={};var _e={};var _r={};var FILTER_SEP='\1';var _c={};var widget_files={'_f.FrmContainer':'form.compressed.js','_c.CalendarPopup':'widgets/form/date_picker.js','_r.ReportContainer':'report.compressed.js','_p.PrintQuery':'widgets/print_query.js','Calendar':'widgets/calendar.js','Recommendation':'widgets/recommend.js','RatingWidget':'widgets/rating.js'}
var frms={};var cur_frm=null;var pscript={};var validated=true;var validation_message='';var tinymce_loaded=null;var cur_autosug=null;
/*
 *	lib/js/legacy/utils/datatype.js
 */
var startup_list=[];wn.utils.full_name=function(fn,ln){return fn+(ln?' ':'')+(ln?ln:'')}
function fmt_money(v){if(v==null||v=='')return'0.00';v=(v+'').replace(/,/g,'');v=parseFloat(v);if(isNaN(v)){return'';}else{var cp=wn.control_panel;var val=2;if(cp.currency_format=='Millions')val=3;v=v.toFixed(2);var delimiter=",";amount=v+'';var a=amount.split('.',2)
var d=a[1];var i=parseInt(a[0]);if(isNaN(i)){return'';}
var minus='';if(v<0){minus='-';}
i=Math.abs(i);var n=new String(i);var a=[];if(n.length>3)
{var nn=n.substr(n.length-3);a.unshift(nn);n=n.substr(0,n.length-3);while(n.length>val)
{var nn=n.substr(n.length-val);a.unshift(nn);n=n.substr(0,n.length-val);}}
if(n.length>0){a.unshift(n);}
n=a.join(delimiter);if(d.length<1){amount=n;}
else{amount=n+'.'+d;}
amount=minus+amount;return amount;}}
function toTitle(str){var word_in=str.split(" ");var word_out=[];for(w in word_in){word_out[w]=word_in[w].charAt(0).toUpperCase()+word_in[w].slice(1);}
return word_out.join(" ");}
function is_null(v){if(v==null){return 1}else if(v==0){if((v+'').length>=1)return 0;else return 1;}else{return 0}}
function $s(ele,v,ftype,fopt){if(v==null)v='';if(ftype=='Text'||ftype=='Small Text'){ele.innerHTML=v?v.replace(/\n/g,'<br>'):'';}else if(ftype=='Date'){v=dateutil.str_to_user(v);if(v==null)v=''
ele.innerHTML=v;}else if(ftype=='Link'&&fopt){ele.innerHTML='';doc_link(ele,fopt,v);}else if(ftype=='Currency'){ele.style.textAlign='right';if(is_null(v))
ele.innerHTML='';else
ele.innerHTML=fmt_money(v);}else if(ftype=='Int'){ele.style.textAlign='right';ele.innerHTML=v;}else if(ftype=='Check'){if(v)ele.innerHTML='<img src="lib/images/ui/tick.gif">';else ele.innerHTML='';}else{ele.innerHTML=v;}}
function clean_smart_quotes(s){if(s){s=s.replace(/\u2018/g,"'");s=s.replace(/\u2019/g,"'");s=s.replace(/\u201c/g,'"');s=s.replace(/\u201d/g,'"');s=s.replace(/\u2013/g,'-');s=s.replace(/\u2014/g,'--');}
return s;}
function copy_dict(d){var n={};for(var k in d)n[k]=d[k];return n;}
function $p(ele,top,left){ele.style.position='absolute';ele.style.top=top+'px';ele.style.left=left+'px';}
function replace_newlines(t){return t?t.replace(/\n/g,'<br>'):'';}
function cstr(s){if(s==null)return'';return s+'';}
function flt(v,decimals){if(v==null||v=='')return 0;v=(v+'').replace(/,/g,'');v=parseFloat(v);if(isNaN(v))
v=0;if(decimals!=null)
return v.toFixed(decimals);return v;}
function esc_quotes(s){if(s==null)s='';return s.replace(/'/,"\'");}
var crop=function(s,len){if(s.length>len)
return s.substr(0,len-3)+'...';else
return s;}
var strip=function(s,chars){var s=lstrip(s,chars)
s=rstrip(s,chars);return s;}
var lstrip=function(s,chars){if(!chars)chars=['\n','\t',' '];var first_char=s.substr(0,1);while(in_list(chars,first_char)){var s=s.substr(1);first_char=s.substr(0,1);}
return s;}
var rstrip=function(s,chars){if(!chars)chars=['\n','\t',' '];var last_char=s.substr(s.length-1);while(in_list(chars,last_char)){var s=s.substr(0,this.length-1);last_char=s.substr(this.length-1);}
return s;}
function repl_all(s,s1,s2){var idx=s.indexOf(s1);while(idx!=-1){s=s.replace(s1,s2);idx=s.indexOf(s1);}
return s;}
function repl(s,dict){if(s==null)return'';for(key in dict)s=repl_all(s,'%('+key+')s',dict[key]);return s;}
function keys(obj){var mykeys=[];for(key in obj)mykeys[mykeys.length]=key;return mykeys;}
function values(obj){var myvalues=[];for(key in obj)myvalues[myvalues.length]=obj[key];return myvalues;}
function in_list(list,item){for(var i=0;i<list.length;i++)
if(list[i]==item)return true;return false;}
function has_common(list1,list2){if(!list1||!list2)return false;for(var i=0;i<list1.length;i++){if(in_list(list2,list1[i]))return true;}
return false;}
var inList=in_list;function add_lists(l1,l2){var l=[];for(var k in l1)l.push(l1[k]);for(var k in l2)l.push(l2[k]);return l;}
function docstring(obj){var l=[];for(key in obj){var v=obj[key];if(v!=null){if(typeof(v)==typeof(1)){l[l.length]="'"+key+"':"+(v+'');}else{v=v+'';l[l.length]="'"+key+"':'"+v.replace(/'/g,"\\'").replace(/\n/g,"\\n")+"'";}}}
return"{"+l.join(',')+'}';}
function DocLink(p,doctype,name,onload){var a=$a(p,'span','link_type');a.innerHTML=a.dn=name;a.dt=doctype;a.onclick=function(){loaddoc(this.dt,this.dn,onload)};return a;}
var doc_link=DocLink;var known_numbers={0:'zero',1:'one',2:'two',3:'three',4:'four',5:'five',6:'six',7:'seven',8:'eight',9:'nine',10:'ten',11:'eleven',12:'twelve',13:'thirteen',14:'fourteen',15:'fifteen',16:'sixteen',17:'seventeen',18:'eighteen',19:'nineteen',20:'twenty',30:'thirty',40:'forty',50:'fifty',60:'sixty',70:'seventy',80:'eighty',90:'ninety'}
function in_words(n){var is_million=wn.control_panel.currency_format=='Millions'?1:0;n=cint(n)
if(known_numbers[n])return known_numbers[n];var bestguess=n+'';var remainder=0
if(n<=20)
alert('Error while converting to words');else if(n<100){return in_words(Math.floor(n/10)*10)+'-'+in_words(n%10);}else if(n<1000){bestguess=in_words(Math.floor(n/100))+' '+'hundred';remainder=n%100;}else if(!is_million){if(n<100000){bestguess=in_words(Math.floor(n/1000))+' '+'thousand';remainder=n%1000;}else if(n<10000000){bestguess=in_words(Math.floor(n/100000))+' '+'lakh';remainder=n%100000;}else{bestguess=in_words(Math.floor(n/10000000))+' '+'crore'
remainder=n%10000000}}else{if(n<1000000){bestguess=in_words(Math.floor(n/1000))+' '+'thousand';remainder=n%1000;}else if(n<1000000000){bestguess=in_words(Math.floor(n/1000000))+' '+'million';remainder=n%1000000;}else{bestguess=in_words(Math.floor(n/1000000000))+' '+'billion'
remainder=n%1000000000}}
if(remainder){if(remainder>=100)comma=','
else comma=''
return bestguess+comma+' '+in_words(remainder);}else{return bestguess;}}
function roundNumber(num,dec){var result=Math.round(num*Math.pow(10,dec))/Math.pow(10,dec);return result;}
/*
 *	lib/js/legacy/utils/browser_detect.js
 */
var appVer=navigator.appVersion.toLowerCase();var is_minor=parseFloat(appVer);var is_major=parseInt(is_minor);var iePos=appVer.indexOf('msie');if(iePos!=-1){is_minor=parseFloat(appVer.substring(iePos+5,appVer.indexOf(';',iePos)))
is_major=parseInt(is_minor);}
var isIE=(iePos!=-1);var isIE6=(isIE&&is_major<=6);var isIE7=(isIE&&is_major>=7);if(/Firefox[\/\s](\d+\.\d+)/.test(navigator.userAgent)){var isFF=1;var ffversion=new Number(RegExp.$1)
if(ffversion>=3)var isFF3=1;else if(ffversion>=2)var isFF2=1;else if(ffversion>=1)var isFF1=1;}
var isSafari=navigator.userAgent.indexOf('Safari')!=-1?1:0;var isChrome=navigator.userAgent.indexOf('Chrome')!=-1?1:0;
/*
 *	lib/js/legacy/utils/datetime.js
 */
function same_day(d1,d2){if(d1.getFullYear()==d2.getFullYear()&&d1.getMonth()==d2.getMonth()&&d1.getDate()==d2.getDate())return true;else return false;}
var month_list=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];var month_last={1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31}
var month_list_full=['January','February','March','April','May','June','July','August','September','October','November','December'];var week_list=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];var week_list_full=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];function int_to_str(i,len){i=''+i;if(i.length<len)for(c=0;c<(len-i.length);c++)i='0'+i;return i}
wn.datetime={str_to_obj:function(d){if(!d)return new Date();var tm=[null,null];if(d.search(' ')!=-1){var tm=d.split(' ')[1].split(':');var d=d.split(' ')[0];}
if(d.search('-')!=-1){var t=d.split('-');return new Date(t[0],t[1]-1,t[2],tm[0],tm[1]);}else if(d.search('/')!=-1){var t=d.split('/');return new Date(t[0],t[1]-1,t[2],tm[0],tm[1]);}else{return new Date();}},obj_to_str:function(d){return d.getFullYear()+'-'+int_to_str(d.getMonth()+1,2)+'-'+int_to_str(d.getDate(),2);},obj_to_user:function(d){return dateutil.str_to_user(dateutil.obj_to_str(d));},get_diff:function(d1,d2){return((d1-d2)/86400000);},add_days:function(d,days){d.setTime(d.getTime()+(days*24*60*60*1000));return d},add_months:function(d,months){dt=dateutil.str_to_obj(d)
new_dt=new Date(dt.getFullYear(),dt.getMonth()+months,dt.getDate())
if(new_dt.getDate()!=dt.getDate()){return dateutil.month_end(new Date(dt.getFullYear(),dt.getMonth()+months,1))}
return dateutil.obj_to_str(new_dt);},month_start:function(){var d=new Date();return d.getFullYear()+'-'+int_to_str(d.getMonth()+1,2)+'-01';},month_end:function(d){if(!d)var d=new Date();var m=d.getMonth()+1;var y=d.getFullYear();last_date=month_last[m];if(m==2&&(y%4)==0&&((y%100)!=0||(y%400)==0))
last_date=29;return y+'-'+int_to_str(m,2)+'-'+last_date;},get_user_fmt:function(){var t=wn.control_panel.date_format;if(!t)t='dd-mm-yyyy';return t;},str_to_user:function(val,no_time_str){var user_fmt=dateutil.get_user_fmt();var time_str='';if(val==null||val=='')return null;if(val.search(':')!=-1){var tmp=val.split(' ');if(tmp[1])
time_str=' '+tmp[1];var d=tmp[0];}else{var d=val;}
if(no_time_str)time_str='';d=d.split('-');if(d.length==3){if(user_fmt=='dd-mm-yyyy')
val=d[2]+'-'+d[1]+'-'+d[0]+time_str;else if(user_fmt=='dd/mm/yyyy')
val=d[2]+'/'+d[1]+'/'+d[0]+time_str;else if(user_fmt=='yyyy-mm-dd')
val=d[0]+'-'+d[1]+'-'+d[2]+time_str;else if(user_fmt=='mm/dd/yyyy')
val=d[1]+'/'+d[2]+'/'+d[0]+time_str;else if(user_fmt=='mm-dd-yyyy')
val=d[1]+'-'+d[2]+'-'+d[0]+time_str;}
return val;},full_str:function(){var d=new Date();return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate()+' '
+d.getHours()+':'+d.getMinutes()+':'+d.getSeconds();},user_to_str:function(d){var user_fmt=this.get_user_fmt();if(user_fmt=='dd-mm-yyyy'){var d=d.split('-');return d[2]+'-'+d[1]+'-'+d[0];}
else if(user_fmt=='dd/mm/yyyy'){var d=d.split('/');return d[2]+'-'+d[1]+'-'+d[0];}
else if(user_fmt=='yyyy-mm-dd'){return d;}
else if(user_fmt=='mm/dd/yyyy'){var d=d.split('/');return d[2]+'-'+d[0]+'-'+d[1];}
else if(user_fmt=='mm-dd-yyyy'){var d=d.split('-');return d[2]+'-'+d[0]+'-'+d[1];}},global_date_format:function(d){if(d.substr)d=this.str_to_obj(d);return d.getDate()+' '+month_list_full[d.getMonth()]+' '+d.getFullYear();},get_today:function(){var today=new Date();var m=(today.getMonth()+1)+'';if(m.length==1)m='0'+m;var d=today.getDate()+'';if(d.length==1)d='0'+d;return today.getFullYear()+'-'+m+'-'+d;},get_cur_time:function(){var d=new Date();var hh=d.getHours()+''
var mm=cint(d.getMinutes()/5)*5+''
return(hh.length==1?'0'+hh:hh)+':'+(mm.length==1?'0'+mm:mm);}}
wn.datetime.only_date=function(val){if(val==null||val=='')return null;if(val.search(':')!=-1){var tmp=val.split(' ');var d=tmp[0].split('-');}else{var d=val.split('-');}
if(d.length==3)
val=d[2]+'-'+d[1]+'-'+d[0];return val;}
wn.datetime.time_to_ampm=function(v){if(!v){var d=new Date();var t=[d.getHours(),cint(d.getMinutes()/5)*5]}else{var t=v.split(':');}
if(t.length!=2){show_alert('[set_time] Incorect time format');return;}
if(cint(t[0])==0)var ret=['12',t[1],'AM'];else if(cint(t[0])<12)var ret=[cint(t[0])+'',t[1],'AM'];else if(cint(t[0])==12)var ret=['12',t[1],'PM'];else var ret=[(cint(t[0])-12)+'',t[1],'PM'];return ret;}
wn.datetime.time_to_hhmm=function(hh,mm,am){if(am=='AM'&&hh=='12'){hh='00';}else if(am=='PM'&&hh!='12'){hh=cint(hh)+12;}
return hh+':'+mm;}
function prettyDate(time){if(!time)return''
var date=new Date((time||"").replace(/-/g,"/").replace(/[TZ]/g," ").replace(/\.[0-9]*/,"")),diff=(((new Date()).getTime()-date.getTime())/1000),day_diff=Math.floor(diff/86400);if(isNaN(day_diff)||day_diff<0)
return'';return day_diff==0&&(diff<60&&"just now"||diff<120&&"1 minute ago"||diff<3600&&Math.floor(diff/60)+" minutes ago"||diff<7200&&"1 hour ago"||diff<86400&&Math.floor(diff/3600)+" hours ago")||day_diff==1&&"Yesterday"||day_diff<7&&day_diff+" days ago"||day_diff<31&&Math.ceil(day_diff/7)+" weeks ago"||day_diff<365&&Math.ceil(day_diff/30)+" months ago"||"more than "+Math.floor(day_diff/365)+" year(s) ago";}
if(typeof jQuery!="undefined")
jQuery.fn.prettyDate=function(){return this.each(function(){var date=prettyDate(this.title);if(date)
jQuery(this).text(date);});};var comment_when=prettyDate;wn.datetime.comment_when=prettyDate;var date=dateutil=wn.datetime;var get_today=wn.datetime.get_today
var time_to_ampm=wn.datetime.time_to_ampm;var time_to_hhmm=wn.datetime.time_to_hhmm;var only_date=wn.datetime.only_date;
/*
 *	lib/js/legacy/utils/dom.js
 */
wn.dom.set_unique_id=function(ele){var id='unique-'+wn.dom.id_count;ele.setAttribute('id',id);wn.dom.id_count++;return id;}
wn.tinymce={add_simple:function(ele,height){if(ele.myid){tinyMCE.execCommand('mceAddControl',true,ele.myid);return;}
ele.myid=wn.dom.set_unique_id(ele);$(ele).tinymce({script_url:'lib/js/legacy/tiny_mce_33/tiny_mce.js',height:height?height:'200px',theme:"advanced",theme_advanced_buttons1:"bold,italic,underline,separator,strikethrough,justifyleft,justifycenter,justifyright,justifyfull,bullist,numlist,outdent,indent,link,unlink,forecolor,backcolor,code,",theme_advanced_buttons2:"",theme_advanced_buttons3:"",theme_advanced_toolbar_location:"top",theme_advanced_toolbar_align:"left",theme_advanced_path:false,theme_advanced_resizing:false});},remove:function(ele){tinyMCE.execCommand('mceRemoveControl',true,ele.myid);},get_value:function(ele){return tinymce.get(ele.myid).getContent();}}
wn.ele={link:function(args){var span=$a(args.parent,'span','link_type',args.style);span.loading_img=$a(args.parent,'img','',{margin:'0px 4px -2px 4px',display:'none'});span.loading_img.src='lib/images/ui/button-load.gif';span.innerHTML=args.label;span.user_onclick=args.onclick;span.onclick=function(){if(!this.disabled)this.user_onclick(this);}
span.set_working=function(){this.disabled=1;$di(this.loading_img);}
span.done_working=function(){this.disabled=0;$dh(this.loading_img);}
return span;}}
function $ln(parent,label,onclick,style){return wn.ele.link({parent:parent,label:label,onclick:onclick,style:style})}
function $btn(parent,label,onclick,style,css_class,is_ajax){wn.require('lib/js/wn/ui/button.js');if(css_class==='green')css_class='primary';return new wn.ui.Button({parent:parent,label:label,onclick:onclick,style:style,is_ajax:is_ajax,css_class:css_class}).btn;}
function addEvent(ev,fn){if(isIE){document.attachEvent('on'+ev,function(){fn(window.event,window.event.srcElement);});}else{document.addEventListener(ev,function(e){fn(e,e.target);},true);}}
$item_normal=function(ele){$y(ele,{padding:'6px 8px',cursor:'pointer',marginRight:'8px',whiteSpace:'nowrap',overflow:'hidden',borderBottom:'1px solid #DDD'});$bg(ele,'#FFF');$fg(ele,'#000');}
$item_active=function(ele){$bg(ele,'#FE8');$fg(ele,'#000');}
$item_selected=function(ele){$bg(ele,'#777');$fg(ele,'#FFF');}
$item_pressed=function(ele){$bg(ele,'#F90');$fg(ele,'#FFF');};(function($){$.fn.set_working=function(){var ele=this.get(0);if(ele.loading_img){$di(ele.loading_img)}else{ele.disabled=1;ele.loading_img=$a(ele.parentNode,'img','',{marginLeft:'4px',marginBottom:'-2px',display:'inline'});ele.loading_img.src='lib/images/ui/button-load.gif';}}
$.fn.done_working=function(){var ele=this.get(0);ele.disabled=0;if(ele.loading_img){$dh(ele.loading_img)};}})(jQuery);function set_opacity(ele,ieop){var op=ieop/100;if(ele.filters){try{ele.filters.item("DXImageTransform.Microsoft.Alpha").opacity=ieop;}catch(e){ele.style.filter='progid:DXImageTransform.Microsoft.Alpha(opacity='+ieop+')';}}else{ele.style.opacity=op;}}
$br=function(ele,r,corners){if(corners){var cl=['top-left','top-right','bottom-right','bottom-left'];for(var i=0;i<4;i++){if(corners[i]){$(ele).css('-moz-border-radius-'+cl[i].replace('-',''),r).css('-webkit-'+cl[i]+'-border-radius',r);}}}else{$(ele).css('-moz-border-radius',r).css('-webkit-border-radius',r).css('border-radius',r);}}
$bs=function(ele,r){$(ele).css('-moz-box-shadow',r).css('-webkit-box-shadow',r).css('box-shadow',r);}
function empty_select(s){if(s.custom_select){s.empty();return;}
if(s.inp)s=s.inp;if(s){var tmplen=s.length;for(var i=0;i<tmplen;i++)s.options[0]=null;}}
function sel_val(s){if(s.custom_select){return s.inp.value?s.inp.value:'';}
if(s.inp)s=s.inp;try{if(s.selectedIndex<s.options.length)return s.options[s.selectedIndex].value;else return'';}catch(err){return'';}}
function add_sel_options(s,list,sel_val,o_style){if(s.custom_select){s.set_options(list)
if(sel_val)s.inp.value=sel_val;return;}
if(s.inp)s=s.inp;for(var i=0,len=list.length;i<len;i++){var o=new Option(list[i],list[i],false,(list[i]==sel_val?true:false));if(o_style)$y(o,o_style);s.options[s.options.length]=o;}}
function cint(v,def){v=v+'';v=lstrip(v,['0']);v=parseInt(v);if(isNaN(v))v=def?def:0;return v;}
function validate_email(id){if(strip(id).search("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")==-1)return 0;else return 1;}
function validate_spl_chars(txt){if(txt.search(/^[a-zA-Z0-9_\- ]*$/)==-1)return 1;else return 0;}
function d2h(d){return cint(d).toString(16);}
function h2d(h){return parseInt(h,16);}
var $n='\n';function set_title(t){document.title=(wn.title_prefix?(wn.title_prefix+' - '):'')+t;}
function $a(parent,newtag,className,cs,innerHTML,onclick){if(parent&&parent.substr)parent=$i(parent);var c=document.createElement(newtag);if(parent)
parent.appendChild(c);if(className){if(newtag.toLowerCase()=='img')
c.src=className
else
c.className=className;}
if(cs)$y(c,cs);if(innerHTML)c.innerHTML=innerHTML;if(onclick)c.onclick=onclick;return c;}
function $a_input(p,in_type,attributes,cs){if(!attributes)attributes={};if(in_type)attributes.type=in_type
if(isIE){var s='<input ';for(key in attributes)
s+=' '+key+'="'+attributes[key]+'"';s+='>'
p.innerHTML=s
var o=p.childNodes[0];}else{var o=$a(p,'input');for(key in attributes)
o.setAttribute(key,attributes[key]);}
if(cs)$y(o,cs);return o;}
function $dh(d){if(d&&d.substr)d=$i(d);if(d&&d.style.display.toLowerCase()!='none')d.style.display='none';}
function $ds(d){if(d&&d.substr)d=$i(d);var t='block';if(d&&in_list(['span','img','button'],d.tagName.toLowerCase()))
t='inline'
if(d&&d.style.display.toLowerCase()!=t)
d.style.display=t;}
function $di(d){if(d&&d.substr)d=$i(d);if(d)d.style.display='inline';}
function $i(id){if(!id)return null;if(id&&id.appendChild)return id;return document.getElementById(id);}
function $t(parent,txt){if(parent.substr)parent=$i(parent);return parent.appendChild(document.createTextNode(txt));}
function $w(e,w){if(e&&e.style&&w)e.style.width=w;}
function $h(e,h){if(e&&e.style&&h)e.style.height=h;}
function $bg(e,w){if(e&&e.style&&w)e.style.backgroundColor=w;}
function $fg(e,w){if(e&&e.style&&w)e.style.color=w;}
function $op(e,w){if(e&&e.style&&w){set_opacity(e,w);}}
function $y(ele,s){if(ele&&s){for(var i in s)ele.style[i]=s[i];};return ele;}
function $yt(tab,r,c,s){var rmin=r;var rmax=r;if(r=='*'){rmin=0;rmax=tab.rows.length-1;}
if(r.search&&r.search('-')!=-1){r=r.split('-');rmin=cint(r[0]);rmax=cint(r[1]);}
var cmin=c;var cmax=c;if(c=='*'){cmin=0;cmax=tab.rows[0].cells.length-1;}
if(c.search&&c.search('-')!=-1){c=c.split('-');rmin=cint(c[0]);rmax=cint(c[1]);}
for(var ri=rmin;ri<=rmax;ri++){for(var ci=cmin;ci<=cmax;ci++)
$y($td(tab,ri,ci),s);}}
function set_style(txt){var se=document.createElement('style');se.type="text/css";if(se.styleSheet){se.styleSheet.cssText=txt;}else{se.appendChild(document.createTextNode(txt));}
document.getElementsByTagName('head')[0].appendChild(se);}
function make_table(parent,nr,nc,table_width,widths,cell_style,table_style){var t=$a(parent,'table');t.style.borderCollapse='collapse';if(table_width)t.style.width=table_width;if(cell_style)t.cell_style=cell_style;for(var ri=0;ri<nr;ri++){var r=t.insertRow(ri);for(var ci=0;ci<nc;ci++){var c=r.insertCell(ci);if(ri==0&&widths&&widths[ci]){c.style.width=widths[ci];}
if(cell_style){for(var s in cell_style)c.style[s]=cell_style[s];}}}
t.append_row=function(){return append_row(this);}
if(table_style)$y(t,table_style);return t;}
function append_row(t,at,style){var r=t.insertRow(at?at:t.rows.length);if(t.rows.length>1){for(var i=0;i<t.rows[0].cells.length;i++){var c=r.insertCell(i);if(style)$y(c,style);}}
return r}
function $td(t,r,c){if(r<0)r=t.rows.length+r;if(c<0)c=t.rows[0].cells.length+c;return t.rows[r].cells[c];}
function $sum(t,cidx){var s=0;if(cidx<1)cidx=t.rows[0].cells.length+cidx;for(var ri=0;ri<t.rows.length;ri++){var c=t.rows[ri].cells[cidx];if(c.div)s+=flt(c.div.innerHTML);else if(c.value)s+=flt(c.value);else s+=flt(c.innerHTML);}
return s;}
function objpos(obj){if(obj.substr)obj=$i(obj);var p=$(obj).offset();return{x:cint(p.left),y:cint(p.top)}}
function get_screen_dims(){var d={};d.w=0;d.h=0;if(typeof(window.innerWidth)=='number'){d.w=window.innerWidth;d.h=window.innerHeight;}else if(document.documentElement&&(document.documentElement.clientWidth||document.documentElement.clientHeight)){d.w=document.documentElement.clientWidth;d.h=document.documentElement.clientHeight;}else if(document.body&&(document.body.clientWidth||document.body.clientHeight)){d.w=document.body.clientWidth;d.h=document.body.clientHeight;}
return d}
function get_page_size(){return[$(document).height(),$(document).width()];}
function get_scroll_top(){var st=0;if(document.documentElement&&document.documentElement.scrollTop)
st=document.documentElement.scrollTop;else if(document.body&&document.body.scrollTop)
st=document.body.scrollTop;return st;}
function get_cookie(c){var t=""+document.cookie;var ind=t.indexOf(c);if(ind==-1||c=="")return"";var ind1=t.indexOf(';',ind);if(ind1==-1)ind1=t.length;return unescape(t.substring(ind+c.length+1,ind1));}
wn.urllib={get_arg:function(name){name=name.replace(/[\[]/,"\\\[").replace(/[\]]/,"\\\]");var regexS="[\\?&]"+name+"=([^&#]*)";var regex=new RegExp(regexS);var results=regex.exec(window.location.href);if(results==null)
return"";else
return decodeURIComponent(results[1]);},get_dict:function(){var d={}
var t=window.location.href.split('?')[1];if(!t)return d;if(t.indexOf('#')!=-1)t=t.split('#')[0];if(!t)return d;t=t.split('&');for(var i=0;i<t.length;i++){var a=t[i].split('=');d[decodeURIComponent(a[0])]=decodeURIComponent(a[1]);}
return d;},get_base_url:function(){var url=window.location.href.split('#')[0].split('?')[0].split('index.html')[0];if(url.substr(url.length-1,1)=='/')url=url.substr(0,url.length-1)
return url},get_file_url:function(file_id){var ac_id=wn.control_panel.account_id;return repl('cgi-bin/getfile.cgi?name=%(fn)s&acx=%(ac)s',{fn:file_id,ac:ac_id})}}
get_url_arg=wn.urllib.get_arg;get_url_dict=wn.urllib.get_dict;var user_img={}
var user_img_queue={};var user_img_loading=[];set_user_img=function(img,username,get_latest,img_id){function set_it(i){if(user_img[username]=='no_img_m')
i.src='lib/images/ui/no_img_m.gif';else if(user_img[username]=='no_img_f')
i.src='lib/images/ui/no_img_f.gif';else{ac_id=wn.control_panel.account_id;i.src=repl('cgi-bin/getfile.cgi?ac=%(ac)s&name=%(fn)s',{fn:user_img[username],ac:ac_id});}}
if(img_id){user_img[username]=img_id;set_it(img);return;}
if(user_img[username]&&!get_latest){set_it(img);}else{if(in_list(user_img_loading,username)){if(!user_img_queue[username])
user_img_queue[username]=[];user_img_queue[username].push(img);return;}
$c('webnotes.profile.get_user_img',{username:username},function(r,rt){delete user_img_loading[user_img_loading.indexOf(username)];user_img[username]=r.message;if(user_img_queue[username]){var q=user_img_queue[username];for(var i in q){set_it(q[i]);}}
set_it(img);},null,1);user_img_loading.push(username);}}
/*
 *	lib/js/legacy/utils/handler.js
 */
var outUrl="index.cgi";var NULL_CHAR='^\5*';function checkResponse(r,on_timeout,no_spinner,freeze_msg){try{if(r.readyState==4&&r.status==200)return true;else return false;}catch(e){msgprint("error:Request timed out, try again");if(on_timeout)
on_timeout();hide_loading();if(freeze_msg)
unfreeze();return false;}}
var pending_req=0;function newHttpReq(){if(!isIE)
var r=new XMLHttpRequest();else if(window.ActiveXObject)
var r=new ActiveXObject("Microsoft.XMLHTTP");return r;}
function $c(command,args,fn,on_timeout,no_spinner,freeze_msg,btn){var req=newHttpReq();ret_fn=function(){if(checkResponse(req,on_timeout,no_spinner,freeze_msg)){if(btn)$(btn).done_working();if(!no_spinner)
hide_loading();var rtxt=req.responseText;try{var r=JSON.parse(rtxt);}catch(e){msgprint('Handler Exception:'+rtxt);return;}
if(freeze_msg)unfreeze();if(!validate_session(r,rtxt))return;if(r.exc){errprint(r.exc);console.log(r.exc);};if(r.server_messages){msgprint(r.server_messages);};if(r.docs){LocalDB.sync(r.docs);}
saveAllowed=true;if(fn)fn(r,rtxt);}}
if(btn)$(btn).set_working();req.onreadystatechange=ret_fn;req.open("POST",outUrl,true);req.setRequestHeader("ENCTYPE","multipart/form-data");req.setRequestHeader("Content-Type","application/x-www-form-urlencoded; charset=UTF-8");args['cmd']=command;req.send(makeArgString(args));if(!no_spinner)set_loading();if(freeze_msg)freeze(freeze_msg,1);}
function validate_session(r,rt){if(r.message=='Logged In'){start_sid=get_cookie('sid');return true;}
if(start_sid&&start_sid!=get_cookie('sid')&&user&&user!='Guest'){page_body.set_session_changed();return;}
if(r.exc&&r.session_status=='Session Expired'){resume_session();return;}
if(r.exc&&r.session_status=='Logged Out'){msgprint('You have been logged out');setTimeout('redirect_to_login()',3000);return;}
if(r.exc&&r.exc_type&&r.exc_type=='PermissionError'){loadpage('_home');}
return true;}
function $c_obj(doclist,method,arg,call_back,no_spinner,freeze_msg,btn){var args={'method':method,'arg':(typeof arg=='string'?arg:JSON.stringify(arg))}
if(typeof doclist=='string')args.doctype=doclist;else args.docs=compress_doclist(doclist)
$c('runserverobj',args,call_back,null,no_spinner,freeze_msg,btn);}
function $c_page(module,page,method,arg,call_back,no_spinner,freeze_msg,btn){if(arg&&!arg.substr)arg=JSON.stringify(arg);$c(module+'.page.'+page+'.'+page+'.'+method,{'arg':arg},call_back,null,no_spinner,freeze_msg,btn);}
wn.call=function(args){if(args.module&&args.page){$c_page(args.module,args.page,args.method,args.args,args.callback,args.no_spinner,false,args.btn);}else if(args.docs){$c_obj(args.doc,args.method,args.args,args.callback,args.no_spinner,false,args.btn);}else{$c(args.method,args.args,args.callback,false,args.no_spinner,false,args.btn);}}
function $c_obj_csv(doclist,method,arg){var args={}
args.cmd='runserverobj';args.as_csv=1;args.method=method;args.arg=arg;if(doclist.substr)
args.doctype=doclist;else
args.docs=compress_doclist(doclist);open_url_post(outUrl,args);}
function my_eval(co){var w=window;if(!w.execScript){if(/Gecko/.test(navigator.userAgent)){eval(co,w);}else{eval.call(w,co);}}else{w.execScript(co);}}
function makeArgString(dict){var varList=[];for(key in dict){varList[varList.length]=key+'='+encodeURIComponent(dict[key]);}
return varList.join('&');}
function open_url_post(URL,PARAMS,new_window){var temp=document.createElement("form");temp.action=URL;temp.method="POST";temp.style.display="none";if(new_window){temp.target='_blank';}
for(var x in PARAMS){var opt=document.createElement("textarea");opt.name=x;opt.value=PARAMS[x];temp.appendChild(opt);}
document.body.appendChild(temp);temp.submit();return temp;}
/*
 *	lib/js/legacy/utils/msgprint.js
 */
var msg_dialog;function msgprint(msg,issmall,callback){if(!msg)return;if(typeof(msg)!='string')
msg=JSON.stringify(msg);if(issmall){show_alert(msg);return;}
if(msg.substr(0,8)=='__small:'){show_alert(msg.substr(8));return;}
if(!msg_dialog){msg_dialog=new Dialog(500,200,"Message");msg_dialog.make_body([['HTML','Msg']])
msg_dialog.onhide=function(){msg_dialog.msg_area.innerHTML='';$dh(msg_dialog.msg_icon);if(msg_dialog.custom_onhide)msg_dialog.custom_onhide();}
$y(msg_dialog.rows['Msg'],{fontSize:'14px',lineHeight:'1.5em',padding:'16px'})
var t=make_table(msg_dialog.rows['Msg'],1,2,'100%',['20px','250px'],{padding:'2px',verticalAlign:'Top'});msg_dialog.msg_area=$td(t,0,1);msg_dialog.msg_icon=$a($td(t,0,0),'img');}
if(!msg_dialog.display)msg_dialog.show();var has_msg=msg_dialog.msg_area.innerHTML?1:0;var m=$a(msg_dialog.msg_area,'div','');if(has_msg)$y(m,{marginTop:'4px'});$dh(msg_dialog.msg_icon);if(msg.substr(0,6).toLowerCase()=='error:'){msg_dialog.msg_icon.src='lib/images/icons/error.gif';$di(msg_dialog.msg_icon);msg=msg.substr(6);}else if(msg.substr(0,8).toLowerCase()=='message:'){msg_dialog.msg_icon.src='lib/images/icons/application.gif';$di(msg_dialog.msg_icon);msg=msg.substr(8);}else if(msg.substr(0,3).toLowerCase()=='ok:'){msg_dialog.msg_icon.src='lib/images/icons/accept.gif';$di(msg_dialog.msg_icon);msg=msg.substr(3);}
m.innerHTML=replace_newlines(msg);if(m.offsetHeight>200){$y(m,{height:'200px',width:'400px',overflow:'auto'})}
msg_dialog.custom_onhide=callback;}
var growl_area;function show_alert(txt){if(!growl_area){growl_area=$a(popup_cont,'div','',{position:'fixed',bottom:'8px',right:'8px',width:'320px',zIndex:10});}
var wrapper=$a(growl_area,'div','',{position:'relative'});var body=$a(wrapper,'div','notice');var c=$a(body,'div','wn-icon ic-round_delete',{cssFloat:'right'});$(c).click(function(){$dh(this.wrapper)});c.wrapper=wrapper;var t=$a(body,'div','',{color:'#FFF'});$(t).html(txt);$(wrapper).hide().fadeIn(1000);}
/*
 *	lib/js/legacy/utils/shortcut.js
 */
(function(jQuery){jQuery.hotkeys={version:"0.8",specialKeys:{8:"backspace",9:"tab",13:"return",16:"shift",17:"ctrl",18:"alt",19:"pause",20:"capslock",27:"esc",32:"space",33:"pageup",34:"pagedown",35:"end",36:"home",37:"left",38:"up",39:"right",40:"down",45:"insert",46:"del",96:"0",97:"1",98:"2",99:"3",100:"4",101:"5",102:"6",103:"7",104:"8",105:"9",106:"*",107:"+",109:"-",110:".",111:"/",112:"f1",113:"f2",114:"f3",115:"f4",116:"f5",117:"f6",118:"f7",119:"f8",120:"f9",121:"f10",122:"f11",123:"f12",144:"numlock",145:"scroll",191:"/",224:"meta"},shiftNums:{"`":"~","1":"!","2":"@","3":"#","4":"$","5":"%","6":"^","7":"&","8":"*","9":"(","0":")","-":"_","=":"+",";":": ","'":"\"",",":"<",".":">","/":"?","\\":"|"}};function keyHandler(handleObj){if(typeof handleObj.data!=="string"){return;}
var origHandler=handleObj.handler,keys=handleObj.data.toLowerCase().split(" ");handleObj.handler=function(event){if(this!==event.target&&(/textarea|select/i.test(event.target.nodeName)||event.target.type==="text")){return;}
var special=event.type!=="keypress"&&jQuery.hotkeys.specialKeys[event.which],character=String.fromCharCode(event.which).toLowerCase(),key,modif="",possible={};if(event.altKey&&special!=="alt"){modif+="alt+";}
if(event.ctrlKey&&special!=="ctrl"){modif+="ctrl+";}
if(event.metaKey&&!event.ctrlKey&&special!=="meta"){modif+="meta+";}
if(event.shiftKey&&special!=="shift"){modif+="shift+";}
if(special){possible[modif+special]=true;}else{possible[modif+character]=true;possible[modif+jQuery.hotkeys.shiftNums[character]]=true;if(modif==="shift+"){possible[jQuery.hotkeys.shiftNums[character]]=true;}}
for(var i=0,l=keys.length;i<l;i++){if(possible[keys[i]]){return origHandler.apply(this,arguments);}}};}
jQuery.each(["keydown","keyup","keypress"],function(){jQuery.event.special[this]={add:keyHandler};});})(jQuery);
/*
 *	lib/js/legacy/utils/printElement.js
 */;(function(window,undefined){var document=window["document"];var $=window["jQuery"];$.fn["printElement"]=function(options){var mainOptions=$.extend({},$.fn["printElement"]["defaults"],options);if(mainOptions["printMode"]=='iframe'){if($.browser.opera||(/chrome/.test(navigator.userAgent.toLowerCase())))
mainOptions["printMode"]='popup';}
$("[id^='printElement_']").remove();return this.each(function(){var opts=$.meta?$.extend({},mainOptions,$(this).data()):mainOptions;_printElement($(this),opts);});};$.fn["printElement"]["defaults"]={"printMode":'iframe',"pageTitle":'',"overrideElementCSS":null,"printBodyOptions":{"styleToAdd":'padding:10px;margin:10px;',"classNameToAdd":''},"leaveOpen":false,"iframeElementOptions":{"styleToAdd":'border:none;position:absolute;width:0px;height:0px;bottom:0px;left:0px;',"classNameToAdd":''}};$.fn["printElement"]["cssElement"]={"href":'',"media":''};function _printElement(element,opts){var html=_getMarkup(element,opts);var popupOrIframe=null;var documentToWriteTo=null;if(opts["printMode"].toLowerCase()=='popup'){popupOrIframe=window.open('about:blank','printElementWindow','width=650,height=440,scrollbars=yes');documentToWriteTo=popupOrIframe.document;}
else{var printElementID="printElement_"+(Math.round(Math.random()*99999)).toString();var iframe=document.createElement('IFRAME');$(iframe).attr({style:opts["iframeElementOptions"]["styleToAdd"],id:printElementID,className:opts["iframeElementOptions"]["classNameToAdd"],frameBorder:0,scrolling:'no',src:'about:blank'});document.body.appendChild(iframe);documentToWriteTo=(iframe.contentWindow||iframe.contentDocument);if(documentToWriteTo.document)
documentToWriteTo=documentToWriteTo.document;iframe=document.frames?document.frames[printElementID]:document.getElementById(printElementID);popupOrIframe=iframe.contentWindow||iframe;}
focus();documentToWriteTo.open();documentToWriteTo.write(html);documentToWriteTo.close();_callPrint(popupOrIframe);};function _callPrint(element){if(element&&element["printPage"])
element["printPage"]();else
setTimeout(function(){_callPrint(element);},50);}
function _getElementHTMLIncludingFormElements(element){var $element=$(element);var elementHtml=$('<div></div>').append($element.clone()).html();return elementHtml;}
function _getBaseHref(){var port=(window.location.port)?':'+window.location.port:'';return window.location.protocol+'//'+window.location.hostname+port+window.location.pathname;}
function _getMarkup(element,opts){var $element=$(element);var elementHtml=_getElementHTMLIncludingFormElements(element);var html=new Array();html.push('<html><head><title>'+opts["pageTitle"]+'</title>');if(opts["overrideElementCSS"]){if(opts["overrideElementCSS"].length>0){for(var x=0;x<opts["overrideElementCSS"].length;x++){var current=opts["overrideElementCSS"][x];if(typeof(current)=='string')
html.push('<link type="text/css" rel="stylesheet" href="'+current+'" >');else
html.push('<link type="text/css" rel="stylesheet" href="'+current["href"]+'" media="'+current["media"]+'" >');}}}
else{$("link",document).filter(function(){return $(this).attr("rel").toLowerCase()=="stylesheet";}).each(function(){html.push('<link type="text/css" rel="stylesheet" href="'+$(this).attr("href")+'" media="'+$(this).attr('media')+'" >');});}
html.push('<base href="'+_getBaseHref()+'" />');html.push('</head><body style="'+opts["printBodyOptions"]["styleToAdd"]+'" class="'+opts["printBodyOptions"]["classNameToAdd"]+'">');html.push('<div class="'+$element.attr('class')+'">'+elementHtml+'</div>');html.push('<script type="text/javascript">function printPage(){focus();print();'+((!$.browser.opera&&!opts["leaveOpen"]&&opts["printMode"].toLowerCase()=='popup')?'close();':'')+'}</script>');html.push('</body></html>');return html.join('');};})(window);
/*
 *	lib/js/wn/ui/dialog.js
 */
wn.widgets.FieldGroup=function(){this.first_button=false;this.make_fields=function(body,fl){wn.require('lib/js/legacy/widgets/form/fields.js');$y(this.body,{padding:'11px'});this.fields_dict={};for(var i=0;i<fl.length;i++){var df=fl[i];var div=$a(body,'div','',{margin:'6px 0px'})
f=make_field(df,null,div,null);f.not_in_form=1;this.fields_dict[df.fieldname]=f
f.refresh();if(df.fieldtype=='Button'&&!this.first_button){$(f.input).addClass('primary');this.first_button=true;}}}
this.get_values=function(){var ret={};var errors=[];for(var key in this.fields_dict){var f=this.fields_dict[key];var v=f.get_value?f.get_value():null;if(f.df.reqd&&!v)
errors.push(f.df.label+' is mandatory');if(v)ret[f.df.fieldname]=v;}
if(errors.length){msgprint('<b>Please check the following Errors</b>\n'+errors.join('\n'));return null;}
return ret;}
this.set_value=function(key,val){var f=this.fields_dict[key];if(f){f.set_input(val);f.refresh_mandatory();}}
this.set_values=function(dict){for(var key in dict){if(this.fields_dict[key]){this.set_value(key,dict[key]);}}}
this.clear=function(){for(key in this.fields_dict){var f=this.fields_dict[key];if(f){f.set_input(f.df['default']||'');}}}}
wn.widgets.Dialog=function(opts){this.opts=opts;this.display=false;this.make=function(opts){if(opts)
this.opts=opts;if(!this.opts.width)this.opts.width=480;this.wrapper=$a(popup_cont,'div','dialog_wrapper');if(this.opts.width)
this.wrapper.style.width=this.opts.width+'px';this.make_head();this.body=$a(this.wrapper,'div','dialog_body');if(this.opts.fields)
this.make_fields(this.body,this.opts.fields);}
this.make_head=function(){var me=this;this.head=$a(this.wrapper,'div','dialog_head');var t=make_table(this.head,1,2,'100%',['100%','16px'],{padding:'2px'});$y($td(t,0,0),{paddingLeft:'16px',fontWeight:'bold',fontSize:'14px',textAlign:'center'});$y($td(t,0,1),{textAlign:'right'});var img=$a($td(t,0,01),'img','',{cursor:'pointer'});img.src='lib/images/icons/close.gif';this.title_text=$td(t,0,0);this.set_title(this.opts.title);img.onclick=function(){if(me.oncancel)me.oncancel();me.hide();}
this.cancel_img=img;}
this.set_title=function(t){this.title_text.innerHTML=t?t:'';}
this.set_postion=function(){var d=get_screen_dims();this.wrapper.style.left=((d.w-cint(this.wrapper.style.width))/2)+'px';this.wrapper.style.top=(get_scroll_top()+60)+'px';top_index++;$y(this.wrapper,{zIndex:top_index});}
this.show=function(){if(this.display)return;this.set_postion()
$ds(this.wrapper);freeze();this.display=true;cur_dialog=this;if(this.onshow)this.onshow();}
this.hide=function(){if(this.onhide)this.onhide();unfreeze();$dh(this.wrapper);if(cur_autosug)cur_autosug.clearSuggestions();this.display=false;cur_dialog=null;}
this.no_cancel=function(){$dh(this.cancel_img);}
if(opts)this.make();}
wn.widgets.Dialog.prototype=new wn.widgets.FieldGroup();keypress_observers.push(new function(){this.notify_keypress=function(e,kc){if(cur_dialog&&kc==27&&!cur_dialog.no_cancel_flag)
cur_dialog.hide();}});
/*
 *	lib/js/legacy/widgets/dialog.js
 */
var cur_dialog;var top_index=91;function Dialog(w,h,title,content){wn.require('lib/js/legacy/widgets/form/fields.js');this.make({width:w,title:title});if(content)this.make_body(content);this.onshow='';this.oncancel='';this.no_cancel_flag=0;this.display=false;this.first_button=false;}
Dialog.prototype=new wn.widgets.Dialog()
Dialog.prototype.make_body=function(content){this.rows={};this.widgets={};for(var i in content)this.make_row(content[i]);}
Dialog.prototype.clear_inputs=function(d){for(var wid in this.widgets){var w=this.widgets[wid];var tn=w.tagName?w.tagName.toLowerCase():'';if(tn=='input'||tn=='textarea'){w.value='';}else if(tn=='select'){sel_val(w.options[0].value);}else if(w.txt){w.txt.value='';}else if(w.input){w.input.value='';}}}
Dialog.prototype.make_row=function(d){var me=this;this.rows[d[1]]=$a(this.body,'div','dialog_row');var row=this.rows[d[1]];if(d[0]!='HTML'){var t=make_table(row,1,2,'100%',['30%','70%']);row.tab=t;var c1=$td(t,0,0);var c2=$td(t,0,1);if(d[0]!='Check'&&d[0]!='Button')
$t(c1,d[1]);}
if(d[0]=='HTML'){if(d[2])row.innerHTML=d[2];this.widgets[d[1]]=row;}
else if(d[0]=='Check'){var i=$a_input(c2,'checkbox','',{width:'20px'});c1.innerHTML=d[1];this.widgets[d[1]]=i;}
else if(d[0]=='Data'){c1.innerHTML=d[1];c2.style.overflow='auto';this.widgets[d[1]]=$a_input(c2,'text');if(d[2])$a(c2,'div','field_description').innerHTML=d[2];}
else if(d[0]=='Link'){c1.innerHTML=d[1];var f=make_field({fieldtype:'Link','label':d[1],'options':d[2]},'',c2,this,0,1);f.not_in_form=1;f.dialog=this;f.refresh();this.widgets[d[1]]=f.input;}
else if(d[0]=='Date'){c1.innerHTML=d[1];var f=make_field({fieldtype:'Date','label':d[1],'options':d[2]},'',c2,this,0,1);f.not_in_form=1;f.refresh();f.dialog=this;this.widgets[d[1]]=f.input;}
else if(d[0]=='Password'){c1.innerHTML=d[1];c2.style.overflow='auto';this.widgets[d[1]]=$a_input(c2,'password');if(d[3])$a(c2,'div','field_description').innerHTML=d[3];}
else if(d[0]=='Select'){c1.innerHTML=d[1];this.widgets[d[1]]=$a(c2,'select','',{width:'160px'})
if(d[2])$a(c2,'div','field_description').innerHTML=d[2];if(d[3])add_sel_options(this.widgets[d[1]],d[3],d[3][0]);}
else if(d[0]=='Text'){c1.innerHTML=d[1];c2.style.overflow='auto';this.widgets[d[1]]=$a(c2,'textarea');if(d[2])$a(c2,'div','field_description').innerHTML=d[2];}
else if(d[0]=='Button'){c2.style.height='32px';var b=$btn(c2,d[1],function(btn){if(btn._onclick)btn._onclick(me)},null,null,1);b.dialog=me;if(!this.first_button){$(b).addClass('primary');this.first_button=true;}
if(d[2]){b._onclick=d[2];}
this.widgets[d[1]]=b;}}
/*
 *	lib/js/legacy/widgets/listing.js
 */
list_opts={cell_style:{padding:'3px 2px'},alt_cell_style:{},head_style:{height:'20px',overflow:'hidden',verticalAlign:'middle',fontWeight:'bold',padding:'1px',fontSize:'13px'},head_main_style:{padding:'0px'},hide_export:1,hide_print:1,hide_refresh:0,hide_rec_label:0,show_calc:1,show_empty_tab:0,no_border:1,append_records:1,table_width:null};function Listing(head_text,no_index,no_loading){wn.require('lib/js/legacy/widgets/form/fields.js');this.start=0;this.page_len=20;this.filters_per_line=7;this.cell_idx=0;this.head_text=head_text?head_text:'Result';this.keyword='records';this.no_index=no_index;this.underline=1;this.no_rec_message='No Result';this.show_cell=null;this.show_result=null;this.colnames=null;this.colwidths=null;this.coltypes=null;this.coloptions=null;this.filters={};this.sort_list={};this.sort_order_dict={};this.sort_heads={};this.is_std_query=false;this.server_call=null;this.no_loading=no_loading;this.opts=copy_dict(list_opts);}
Listing.prototype.make=function(parent){var me=this;this.wrapper=parent;this.filter_wrapper=$a(parent,'div','srs_filter_wrapper');this.filter_area=$a(this.filter_wrapper,'div','srs_filter_area');$dh(this.filter_wrapper);this.btn_area=$a(parent,'div','',{margin:'8px 0px'});this.body_area=$a(parent,'div','srs_body_area');if(!this.opts.hide_rec_label)
this.rec_label=$a(this.body_area,'div','',{margin:'4px 0px',color:'#888'});this.results=$a($a(this.body_area,'div','srs_results_area'),'div');this.fetching_area=$a(this.body_area,'div','',{height:'120px',background:'url("lib/images/ui/square_loading.gif") center no-repeat',display:'none'});this.show_no_records=$a(this.body_area,'div','',{margin:'200px 0px',textAlign:'center',fontSize:'14px',color:'#888',display:'none'});this.show_no_records.innerHTML='No Result';if(this.opts.show_empty_tab)
this.make_result_tab();this.bottom_div=$a(this.body_area,'div','',{paddingTop:'8px'});this.make_toolbar();}
Listing.prototype.make_toolbar=function(){var me=this;this.buttons={};var make_btn=function(label,icon,onclick,bold){var btn=$btn(me.btn_area,label,onclick,{marginRight:'4px'});if(bold)$y(btn,{fontWeight:'bold'});me.buttons[label]=btn;}
if(!this.opts.hide_refresh){make_btn('Refresh','ui-icon-refresh',function(btn){me.start=0;me.run();},1);}
if(this.opts.show_new){make_btn('New ','ui-icon-document',function(){new_doc(me.dt);},1);}
if(this.opts.show_report){make_btn('Report Builder','ui-icon-clipboard',function(){loadreport(me.dt,null,null,null,1);},0);}
if(!this.opts.hide_export){make_btn('Export','ui-icon-circle-arrow-e',function(){me.do_export();});}
if(!this.opts.hide_print){make_btn('Print','ui-icon-print',function(){me.do_print();});}
if(this.opts.show_calc){make_btn('Calc','ui-icon-calculator',function(){me.do_calc();});$dh(me.buttons['Calc'])}
this.loading_img=$a(this.btn_area,'img','',{display:'none',marginBottom:'-2px'});this.loading_img.src='lib/images/ui/button-load.gif';if(!keys(this.buttons).length)
$dh(this.btn_area);}
Listing.prototype.do_print=function(){this.build_query();if(!this.query){alert('No Query!');return;}
args={query:this.query,title:this.head_text,colnames:this.colnames,colwidths:this.colwidths,coltypes:this.coltypes,has_index:(this.no_index?0:1),has_headings:1,check_limit:1,is_simple:1}
wn.require('lib/js/legacy/widgets/print_query.js');_p.print_query=new _p.PrintQuery();_p.print_query.show_dialog(args);}
Listing.prototype.do_calc=function(){show_calc(this.result_tab,this.colnames,this.coltypes,0)}
Listing.prototype.add_filter=function(label,ftype,options,tname,fname,cond){if(!this.filter_area){alert('[Listing] make() must be called before add_filter');}
var me=this;if(!this.filter_set){var h=$a(this.filter_area,'div','',{fontSize:'14px',fontWeight:'bold',marginBottom:'4px'});h.innerHTML='Filter your search';this.filter_area.div=$a(this.filter_area,'div');this.perm=[[1,1],]
this.filters={};}
$ds(this.filter_wrapper);if((!this.inp_tab)||(this.cell_idx==this.filters_per_line)){this.inp_tab=$a(this.filter_area.div,'table','',{width:'100%',tableLayout:'fixed'});this.inp_tab.insertRow(0);for(var i=0;i<this.filters_per_line;i++){this.inp_tab.rows[0].insertCell(i);}
this.cell_idx=0;}
var c=this.inp_tab.rows[0].cells[this.cell_idx];this.cell_idx++;$y(c,{width:cint(100/this.filters_per_line)+'%',textAlign:'left',verticalAlign:'top'});var d1=$a(c,'div','',{fontSize:'11px',marginBottom:'2px'});d1.innerHTML=label;if(ftype=='Link')d1.innerHTML+=' <img src="lib/images/icons/link.png" style="margin-bottom:-5px" title="Link">';var d2=$a(c,'div');if(in_list(['Text','Small Text','Code','Text Editor','Read Only'],ftype))
ftype='Data';if(ftype=='Select'&&!in_list(options.split('\n'),''))options='\n'+options
var inp=make_field({fieldtype:ftype,'label':label,'options':options,no_buttons:1},'',d2,this,0,1);inp.not_in_form=1;inp.report=this;inp.df.single_select=1;inp.parent_cell=c;inp.parent_tab=this.input_tab;$y(inp.wrapper,{width:'95%'});inp.refresh();inp.tn=tname;inp.fn=fname;inp.condition=ftype=='Data'?'like':cond;var me=this;inp.onchange=function(){me.start=0;}
this.filters[label]=inp;this.filter_set=1;}
Listing.prototype.remove_filter=function(label){var inp=this.filters[label];inp.parent_tab.rows[0].deleteCell(inp.parent_cell.cellIndex);delete this.filters[label];}
Listing.prototype.remove_all_filters=function(){for(var k in this.filters)this.remove_filter(k);$dh(this.filter_wrapper);}
Listing.prototype.add_sort=function(ci,fname){this.sort_list[ci]=fname;}
Listing.prototype.has_data=function(){return this.n_records;}
Listing.prototype.set_default_sort=function(fname,sort_order){this.sort_order=sort_order;this.sort_order_dict[fname]=sort_order;this.sort_by=fname;if(this.sort_heads[fname])
this.sort_heads[fname].set_sorting_as(sort_order);}
Listing.prototype.set_sort=function(cell,ci,fname){var me=this;$y(cell.sort_cell,{width:'18px'});cell.sort_img=$a(cell.sort_cell,'img');cell.fname=fname;$dh(cell.sort_img);cell.set_sort_img=function(order){var t='images/icons/sort_desc.gif';if(order=='ASC'){t='images/icons/sort_asc.gif';}
this.sort_img.src=t;}
cell.set_sorting_as=function(order){me.sort_order=order;me.sort_by=this.fname
me.sort_order_dict[this.fname]=order;this.set_sort_img(order)
if(me.cur_sort){$y(me.cur_sort,{backgroundColor:"#FFF"});$dh(me.cur_sort.sort_img);}
me.cur_sort=this;$y(this,{backgroundColor:"#DDF"});$di(this.sort_img);}
$y(cell.label_cell,{color:'#44A',cursor:'pointer'});cell.set_sort_img(me.sort_order_dict[fname]?me.sort_order_dict[fname]:'ASC');cell.onmouseover=function(){$di(this.sort_img);}
cell.onmouseout=function(){if(this!=me.cur_sort)
$dh(this.sort_img);}
cell.onclick=function(){this.set_sorting_as((me.sort_order_dict[fname]=='ASC')?'DESC':'ASC');me.run();}
this.sort_heads[fname]=cell;}
Listing.prototype.do_export=function(){this.build_query();var me=this;me.cn=[];if(this.no_index)
me.cn=this.colnames;else{for(var i=1;i<this.colnames.length;i++)
me.cn.push(this.colnames[i]);}
var q=export_query(this.query,function(query){export_csv(query,me.head_text,null,1,null,me.cn);});}
Listing.prototype.build_query=function(){if(this.get_query)this.get_query(this);if(!this.query){alert('No Query!');return;}
if(!this.prefix)this.prefix='tab';var cond=[];for(var i in this.filters){var f=this.filters[i];var val=f.get_value();var c=f.condition;if(!c)c='=';if(val&&c.toLowerCase()=='like')val+='%';if(f.tn&&val&&!in_list(['All','Select...',''],val))
cond.push(repl(' AND `%(prefix)s%(dt)s`.%(fn)s %(condition)s "%(val)s"',{prefix:this.prefix,dt:f.tn,fn:f.fn,condition:c,val:val}));}
if(cond){this.query+=NEWLINE+cond.join(NEWLINE)
if(this.query_max)
this.query_max+=NEWLINE+cond.join(NEWLINE)}
if(this.group_by)
this.query+=' '+this.group_by+' ';if(this.sort_by&&this.sort_order){this.query+=NEWLINE+' ORDER BY `'+this.sort_by+'` '+this.sort_order;}
if(this.show_query)msgprint(this.query);}
Listing.prototype.set_rec_label=function(total,cur_page_len){if(this.opts.hide_rec_label)
return;else if(total==-1)
this.rec_label.innerHTML='Fetching...'
else if(total>0)
this.rec_label.innerHTML=repl('Total %(total)s %(keyword)s. Showing %(start)s to %(end)s',{total:total,start:cint(this.start)+1,end:cint(this.start)+cint(cur_page_len),keyword:this.keyword});else if(total==null)
this.rec_label.innerHTML=''
else if(total==0)
this.rec_label.innerHTML=this.no_rec_message;}
Listing.prototype.run=function(run_callback){this.build_query();var q=this.query;var me=this;if(this.max_len&&this.start>=this.max_len)this.start-=this.page_len;q+=' LIMIT '+this.start+','+this.page_len;var call_back=function(r,rt){$dh(me.loading_img);me.max_len=r.n_values;if(r.values&&r.values.length){me.n_records=r.values.length;var nc=r.values[0].length;if(me.colwidths)nc=me.colwidths.length-(me.no_index?0:1);if(me.opts.append_records&&me.start!=0){me.append_rows(r.values.length);}else{me.clear_tab();if(!me.show_empty_tab){me.remove_result_tab();me.make_result_tab(r.values.length);}}
me.refresh(r.values.length,nc,r.values,r.n_values);me.total_records=r.n_values;me.set_rec_label(r.n_values,r.values.length);}else{me.n_records=0;me.set_rec_label(0);me.clear_tab();if(!me.opts.append_records){if(me.show_empty_tab){me.clear_tab();}else{me.remove_result_tab();me.make_result_tab(0);if(me.opts.show_no_records_label){$ds(me.show_no_records);}}}}
$ds(me.results);if(run_callback)run_callback();if(me.onrun)me.onrun();}
$dh(me.show_no_records);this.set_rec_label(-1);$di(this.loading_img);if(this.server_call){this.server_call(this,call_back);}else{args={query_max:(this.query_max?this.query_max:'')}
if(this.is_std_query)args.query=q;else args.simple_query=q;if(this.opts.formatted)args.formatted=1;$c('webnotes.widgets.query_builder.runquery',args,call_back,null,this.no_loading);}}
Listing.prototype.remove_result_tab=function(){if(!this.result_tab)return;this.result_tab.parentNode.removeChild(this.result_tab);delete this.result_tab;}
Listing.prototype.reset_tab=function(){this.remove_result_tab();this.make_result_tab();}
Listing.prototype.make_result_tab=function(nr){if(this.result_tab)return;if(!this.colwidths)alert("Listing: Must specify column widths");var has_headrow=this.colnames?1:0;if(nr==null)nr=this.page_len;nr+=has_headrow;var nc=this.colwidths.length;var t=make_table(this.results,nr,nc,(this.opts.table_width?this.opts.table_width:'100%'),this.colwidths,{padding:'0px'});t.className='srs_result_tab';this.result_tab=t;$y(t,{borderCollapse:'collapse'});if(this.opts.table_width){$y(this.results,{overflowX:'auto'});$y(t,{tableLayout:'fixed'});}
if(has_headrow){this.make_headings(t,nr,nc);if(this.sort_by&&this.sort_heads[this.sort_by]){this.sort_heads[this.sort_by].set_sorting_as(this.sort_order);}}
this.set_table_style();if(this.opts.no_border==1){$y(t,{border:'0px'});}
this.result_tab=t;}
Listing.prototype.set_table_style=function(){var t=this.result_tab;for(var ri=(this.colnames?1:0);ri<t.rows.length;ri++){for(var ci=0;ci<t.rows[ri].cells.length;ci++){if(this.opts.cell_style)$y($td(t,ri,ci),this.opts.cell_style);if(this.opts.alt_cell_style&&(ri%2))$y($td(t,ri,ci),this.opts.alt_cell_style);if(this.opts.show_empty_tab&&!$td(t,ri,ci).innerHTML)$td(t,ri,ci).innerHTML='&nbsp;';}}}
Listing.prototype.append_rows=function(nr){for(var i=0;i<nr;i++){append_row(this.result_tab);}
this.set_table_style();}
Listing.prototype.clear_tab=function(){$dh(this.results);if(this.result_tab){var nr=this.result_tab.rows.length;var nc=this.result_tab.rows[0].cells.length;for(var ri=(this.colnames?1:0);ri<nr;ri++)
for(var ci=0;ci<nc;ci++)
$td(this.result_tab,ri,ci).innerHTML=(this.opts.show_empty_tab?'&nbsp;':'');}}
Listing.prototype.clear=function(){this.rec_label.innerHTML='';this.clear_tab();}
Listing.prototype.refresh_calc=function(){if(!this.opts.show_calc)return;if(has_common(this.coltypes,['Currency','Int','Float'])){$di(this.buttons['Calc']);}else{$dh(this.buttons['Calc']);}}
Listing.prototype.refresh=function(nr,nc,d,n_values){this.refresh_more_button(nr,n_values);this.refresh_calc();if(this.show_result)
this.show_result();else{if(nr){var start=this.result_tab.rows.length-nr;for(var ri=start;ri<start+nr;ri++){var c0=$td(this.result_tab,ri,0);if(!this.no_index){c0.innerHTML=cint(this.start)+cint(ri-start)+1;}
for(var ci=0;ci<nc;ci++){var c=$td(this.result_tab,ri,ci+(this.no_index?0:1));if(c){c.innerHTML='';if(this.show_cell)this.show_cell(c,ri-start,ci,d);else this.std_cell(c,ri-start,ci,d);}}}}}}
Listing.prototype.refresh_more_button=function(nr,n_values){var me=this;if(this.more_btn){$dh(this.more_btn);}
if((this.start+nr)==this.max_len||(!this.max_len&&nr<this.page_len)){}else if(nr){if(!this.more_btn){$y(this.bottom_div,{margin:'8px 0px 16px 0px',textAlign:'center'});this.more_btn=$btn(this.bottom_div,'Show more results...',function(){me.start=me.start+me.page_len;me.more_btn.set_working();me.run(function(){me.more_btn.done_working();});},{fontSize:'14px'},0,1);$y(this.more_btn.loading_img,{marginBottom:'0px'});}
$di(this.more_btn);}}
Listing.prototype.make_headings=function(t,nr,nc){for(var ci=0;ci<nc;ci++){var tmp=make_table($td(t,0,ci),1,2,'100%',['','0px'],this.opts.head_style);$y(tmp,{tableLayout:'fixed',borderCollapse:'collapse'});$y($td(t,0,ci),this.opts.head_main_style);$td(t,0,ci).sort_cell=$td(tmp,0,1);$td(t,0,ci).label_cell=$td(tmp,0,0);$td(tmp,0,1).style.padding='0px';$td(tmp,0,0).innerHTML=this.colnames[ci]?this.colnames[ci]:'&nbsp;';if(this.sort_list[ci])this.set_sort($td(t,0,ci),ci,this.sort_list[ci]);var div=$a($td(t,0,ci),'div');$td(t,0,ci).style.borderBottom='1px solid #CCC';if(this.coltypes&&this.coltypes[ci]&&in_list(['Currency','Float','Int'],this.coltypes[ci]))$y($td(t,0,ci).label_cell,{textAlign:'right'})}}
Listing.prototype.std_cell=function(cell,ri,ci,d){var has_headrow=this.colnames?1:0;cell.div=$a(cell,'div');$s(cell.div,d[ri][ci],this.coltypes?this.coltypes[ci+(this.no_index?0:1)]:null,this.coloptions?this.coloptions[ci+(this.no_index?0:1)]:null);}
/*
 *	lib/js/wn/ui/listing.js
 */
wn.widgets.Listing=function(opts){this.opts=opts;this.page_length=20;this.btns={};this.start=0;var me=this;this.make=function(opts){this.wrapper=$a(this.opts.parent,'div');this.filters_area=$a(this.wrapper,'div','listing-filters');this.toolbar_area=$a(this.wrapper,'div','listing-toolbar');this.results_area=$a(this.wrapper,'div','listing-results');this.more_button_area=$a(this.wrapper,'div','listing-more');this.no_results_area=$a(this.wrapper,'div','help_box',{display:'none'},(this.opts.no_result_message?this.opts.no_result_message:'No results'));if(opts)this.opts=opts;this.page_length=this.opts.page_length?this.opts.page_length:this.page_length;this.make_toolbar();this.make_filters();this.make_more_button();}
this.make_filters=function(){if(this.opts.filters){$ds(this.filters_area);this.filters=new wn.widgets.FieldGroup(this.filters_area,this.opts.fields);}}
this.make_toolbar=function(){if(!this.opts.hide_refresh){this.ref_img=$a(this.toolbar_area,'span','link_type',{color:'#888'},'[refresh]');this.ref_img.onclick=function(){me.run();}
this.loading_img=$a(this.toolbar_area,'img','lib/images/ui/button-load.gif',{display:'none',marginLeft:'3px',marginBottom:'-2px'});}
if(this.opts.new_doctype){this.new_btn=$btn(this.toolbar_area,'New '+get_doctype_label(this.opts.new_doctype),function(){newdoc(me.opts.new_doctype,me.opts.new_doc_onload,me.opts.new_doc_indialog,me.opts.new_doc_onsave);},{marginLeft:'7px'});}}
this.make_more_button=function(){this.more_btn=$btn(this.more_button_area,'More...',function(){me.more_btn.set_working();me.run(function(){me.more_btn.done_working();},1);},'',0,1);$y(this.more_btn.loading_img,{marginBottom:'0px'});}
this.clear=function(){this.results_area.innerHTML='';this.table=null;$ds(this.results_area);$dh(this.no_results_area);}
this.make_results=function(r,rt){if(this.start==0)this.clear();$dh(this.more_button_area);if(this.loading_img)$dh(this.loading_img)
if(r.values&&r.values.length){this.values=r.values;var m=Math.min(r.values.length,this.page_length);for(var i=0;i<m;i++){var row=this.add_row();this.opts.render_row(row,r.values[i],this,i);}
this.start+=m;if(r.values.length>this.page_length)$ds(this.more_button_area);}else{if(this.start==0){$dh(this.results_area);$ds(this.no_results_area);}}
if(this.onrun)this.onrun();if(this.opts.onrun)this.opts.onrun();}
this.add_row=function(){return $a(this.results_area,'div','',(opts.cell_style?opts.cell_style:{padding:'3px 0px'}));}
this.run=function(callback,append){if(callback)
this.onrun=callback;if(!append)
this.start=0;this.query=this.opts.get_query?this.opts.get_query():this.opts.query;this.add_limits();args={query_max:this.query_max||this.opts.query_max||''}
args.simple_query=this.query;args.as_dict=1;if(this.loading_img)$di(this.loading_img);wn.call({method:'webnotes.widgets.query_builder.runquery',args:args,callback:function(r,rt){me.make_results(r,rt)},no_spinner:this.opts.no_loading,btn:this.opts.run_btn});}
this.refresh=this.run;this.add_limits=function(){this.query+=' LIMIT '+this.start+','+(this.page_length+1);}
if(opts)this.make();}
/*
 *	lib/js/legacy/widgets/layout.js
 */
function Layout(parent,width){if(parent&&parent.substr){parent=$i(parent);}
this.wrapper=$a(parent,'div','',{display:'none'});if(width){this.width=this.wrapper.style.width;}
this.myrows=[];}
Layout.prototype.addrow=function(){this.cur_row=new LayoutRow(this,this.wrapper);this.myrows[this.myrows.length]=this.cur_row;return this.cur_row}
Layout.prototype.addsubrow=function(){this.cur_row=new LayoutRow(this,this.cur_row.main_body);this.myrows[this.myrows.length]=this.cur_row;return this.cur_row}
Layout.prototype.addcell=function(width){return this.cur_row.addCell(width);}
Layout.prototype.setcolour=function(col){$bg(cc,col);}
Layout.prototype.show=function(){$ds(this.wrapper);}
Layout.prototype.hide=function(){$dh(this.wrapper);}
Layout.prototype.close_borders=function(){if(this.with_border){this.myrows[this.myrows.length-1].wrapper.style.borderBottom='1px solid #000';}}
function LayoutRow(layout,parent){this.layout=layout;this.wrapper=$a(parent,'div');this.main_head=$a(this.wrapper,'div');this.main_body=$a(this.wrapper,'div');if(layout.with_border){this.wrapper.style.border='1px solid #000';this.wrapper.style.borderBottom='0px';}
this.header=$a(this.main_body,'div','',{padding:(layout.with_border?'0px 8px':'0px')});this.body=$a(this.main_body,'div');this.table=$a(this.body,'table','',{width:'100%',borderCollapse:'collapse'});this.row=this.table.insertRow(0);this.mycells=[];}
LayoutRow.prototype.hide=function(){$dh(this.wrapper);}
LayoutRow.prototype.show=function(){$ds(this.wrapper);}
LayoutRow.prototype.addCell=function(wid){var lc=new LayoutCell(this.layout,this,wid);this.mycells[this.mycells.length]=lc;return lc;}
function LayoutCell(layout,layoutRow,width){if(width){var w=width+'';if(w.substr(w.length-2,2)!='px'){if(w.substr(w.length-1,1)!="%"){width=width+'%'};}}
this.width=width;this.layout=layout;var cidx=layoutRow.row.cells.length;this.cell=layoutRow.row.insertCell(cidx);this.cell.style.verticalAlign='top';this.set_width(layoutRow.row,width);var h=$a(this.cell,'div','',{padding:(layout.with_border?'0px 8px':'0px')});this.wrapper=$a(this.cell,'div','',{padding:(layout.with_border?'8px':'8px 0px')});layout.cur_cell=this.wrapper;layout.cur_cell.header=h;}
LayoutCell.prototype.set_width=function(row,width){var w=100;var n_cells=row.cells.length;var cells_with_no_width=n_cells;if(width){$y(row.cells[n_cells-1],{width:cint(width)+'%'})}else{row.cells[n_cells-1].estimated_width=1;}
for(var i=0;i<n_cells;i++){if(!row.cells[i].estimated_width){w=w-cint(row.cells[i].style.width);cells_with_no_width--;}}
for(var i=0;i<n_cells;i++){if(row.cells[i].estimated_width)
$y(row.cells[i],{width:cint(w/cells_with_no_width)+'%'})}}
LayoutCell.prototype.show=function(){$ds(this.wrapper);}
LayoutCell.prototype.hide=function(){$dh(this.wrapper);}
/*
 *	lib/js/legacy/widgets/tabbedpage.js
 */
function TabbedPage(parent,only_labels){this.tabs={};this.items=this.tabs
this.cur_tab=null;this.label_wrapper=$a(parent,'div','box_label_wrapper',{marginTop:'16px'});this.label_body=$a(this.label_wrapper,'div','box_label_body');this.label_area=$a(this.label_body,'ul','box_tabs');if(!only_labels)this.body_area=$a(parent,'div','',{backgroundColor:'#FFF'});else this.body_area=null;this.add_item=function(label,onclick,no_body,with_heading){this.add_tab(label,onclick,no_body,with_heading);return this.items[label];}}
TabbedPage.prototype.add_tab=function(n,onshow,no_body,with_heading){var tab=$a(this.label_area,'li');tab.label=$a(tab,'a');tab.label.innerHTML=n;if(this.body_area&&!no_body){tab.tab_body=$a(this.body_area,'div');$dh(tab.tab_body);tab.body=tab.tab_body;}else{tab.tab_body=null;}
tab.onshow=onshow;var me=this;tab.collapse=function(){if(this.tab_body)$dh(this.tab_body);this.className='';if(hide_autosuggest)
hide_autosuggest();}
tab.set_selected=function(){if(me.cur_tab)me.cur_tab.collapse();this.className='box_tab_selected';$op(this,100);me.cur_tab=this;}
tab.expand=function(arg){this.set_selected();if(this.tab_body)$ds(this.tab_body);if(this.onshow)this.onshow(arg);}
tab.onmouseover=function(){if(me.cur_tab!=this)this.className='box_tab_mouseover';}
tab.onmouseout=function(){if(me.cur_tab!=this)this.className=''}
tab.hide=function(){this.collapse();$dh(this);}
tab.show=function(){$ds(this);}
tab.onclick=function(){this.expand();}
this.tabs[n]=tab;return tab;}
function TrayPage(parent,height,width,width_body){var me=this;if(!width)width=(100/8)+'%';this.body_style={margin:'4px 8px'}
this.cur_item=null;this.items={};this.tabs=this.items
this.tab=make_table($a(parent,'div'),1,2,'100%',[width,width_body]);$y($td(this.tab,0,0),{backgroundColor:this.tray_bg,width:width});this.body=$a($td(this.tab,0,1),'div');if(height){$y(this.body,{height:height,overflow:'auto'});}
this.add_item=function(label,onclick,no_body,with_heading){this.items[label]=new TrayItem(me,label,onclick,no_body,with_heading);return this.items[label];}}
function TrayItem(tray,label,onclick,no_body,with_heading){this.label=label;this.onclick=onclick;var me=this;this.ldiv=$a($td(tray.tab,0,0),'div');$item_normal(this.ldiv);if(!no_body){this.wrapper=$a(tray.body,'div','',tray.body_style);if(with_heading){this.header=$a(this.wrapper,'div','sectionHeading',{marginBottom:'16px',paddingBottom:'0px'});this.header.innerHTML=label;}
this.body=$a(this.wrapper,'div');this.tab_body=this.body;$dh(this.wrapper);}
$(this.ldiv).html(label).hover(function(){if(tray.cur_item.label!=this.label)$item_active(this);},function(){if(tray.cur_item.label!=this.label)$item_normal(this);}).click(function(){me.expand();})
this.ldiv.label=label;this.ldiv.setAttribute('title',label);this.ldiv.onmousedown=function(){$item_pressed(this);}
this.ldiv.onmouseup=function(){$item_selected(this);}
this.expand=function(){if(tray.cur_item)tray.cur_item.collapse();if(me.wrapper)$ds(me.wrapper);if(me.onclick)me.onclick(me.label);me.show_as_expanded();}
this.show_as_expanded=function(){$item_selected(me.ldiv);tray.cur_item=me;}
this.collapse=function(){if(me.wrapper)$dh(me.wrapper);$item_normal(me.ldiv);}
this.hide=function(){me.collapse();$dh(me.ldiv);}
this.show=function(){$ds(me.ldiv);}}
/*
 *	lib/js/legacy/webpage/page_header.js
 */
var def_ph_style={wrapper:{marginBottom:'16px',backgroundColor:'#EEE'},main_heading:{},sub_heading:{marginBottom:'8px',color:'#555',display:'none'},separator:{borderTop:'3px solid #444'},toolbar_area:{padding:'3px 0px',display:'none',borderBottom:'1px solid #AAA'}}
function PageHeader(parent,main_text,sub_text){this.wrapper=$a(parent,'div','page_header');this.t1=make_table($a(this.wrapper,'div','',def_ph_style.wrapper.backgroundColor),1,2,'100%',[null,'100px'],{padding:'2px'});$y(this.t1,{borderCollapse:'collapse'})
this.lhs=$td(this.t1,0,0);this.main_head=$a(this.lhs,'h1','',def_ph_style.main_heading);this.sub_head=$a(this.lhs,'h4','',def_ph_style.sub_heading);this.separator=$a(this.wrapper,'div','',def_ph_style.separator);this.toolbar_area=$a(this.wrapper,'div','',def_ph_style.toolbar_area);this.padding_area=$a(this.wrapper,'div','',{padding:'3px'});$y($td(this.t1,0,1),{textAlign:'right',padding:'3px'});this.close_btn=$a($td(this.t1,0,1),'span','close',{},'&#215;');this.close_btn.onclick=function(){nav_obj.show_last_open();};if(main_text)this.main_head.innerHTML=main_text;if(sub_text)this.sub_head.innerHTML=sub_text;this.buttons={};this.buttons2={};}
PageHeader.prototype.add_button=function(label,fn,bold,icon,green){var tb=this.toolbar_area;if(this.buttons[label])return;var btn=$btn(tb,label,fn,{marginRight:'4px'},(green?'primary':''));if(bold)$y(btn,{fontWeight:'bold'});this.buttons[label]=btn;$ds(this.toolbar_area);return btn;}
PageHeader.prototype.clear_toolbar=function(){this.toolbar_area.innerHTML='';this.buttons={};}
PageHeader.prototype.make_buttonset=function(){$(this.toolbar_area).buttonset();}
/*
 *	lib/js/legacy/widgets/select.js
 */
function SelectWidget(parent,options,width,editable,bg_color){var me=this;this.inp=$a(parent,'select');if(options)add_sel_options(this.inp,options);if(width)$y(this.inp,{width:width});this.set_width=function(w){$y(this.inp,{width:w})};this.set_options=function(o){add_sel_options(this.inp,o);}
this.inp.onchange=function(){if(me.onchange)me.onchange(this);}
return;}
/*
 *	lib/js/legacy/widgets/tags.js
 */
_tags={dialog:null,color_map:{},all_tags:[],colors:{'Default':'#add8e6'}}
TagList=function(parent,start_list,dt,dn,static,onclick){this.start_list=start_list?start_list:[];this.tag_list=[];this.dt=dt;this.onclick=onclick;this.dn=dn;this.static;this.parent=parent;this.make_body();}
TagList.prototype.make=function(parent){for(var i=0;i<this.start_list.length;i++){if(this.start_list[i])
new SingleTag({parent:this.body,label:this.start_list[i],dt:this.dt,dn:this.dn,fieldname:'_user_tags',static:this.static,taglist:this,onclick:this.onclick});}}
TagList.prototype.make_body=function(){var div=$a(this.parent,'span','',{margin:'3px 0px',padding:'3px 0px'});this.body=$a(div,'span','',{marginRight:'4px'});this.add_tag_area=$a(div,'span');this.make_add_tag();this.make();}
TagList.prototype.add_tag=function(label,static,fieldname,color){if(!label)return;if(in_list(this.tag_list,label))return;var tag=new SingleTag({parent:this.body,label:label,dt:this.dt,dn:this.dn,fieldname:fieldname,static:static,taglist:this,color:color,onclick:this.onclick});}
TagList.prototype.make_add_tag=function(){var me=this;this.add_tag_span=$a(this.add_tag_area,'span','',{color:'#888',textDecoration:'underline',cursor:'pointer',marginLeft:'4px',fontSize:'11px'});this.add_tag_span.innerHTML='Add tag';this.add_tag_span.onclick=function(){me.new_tag();}}
TagList.prototype.make_tag_dialog=function(){var me=this;var d=new wn.widgets.Dialog({title:'Add a tag',width:400,fields:[{fieldtype:'Link',fieldname:'tag',label:'Tag',options:'Tag',reqd:1,description:'Max chars (20)',no_buttons:1},{fieldtype:'Button',fieldname:'add',label:'Add'}]})
$(d.fields_dict.tag.input).attr('maxlength',20);d.fields_dict.add.input.onclick=function(){me.save_tag(d);}
return d;}
TagList.prototype.is_text_okay=function(val){if(!val){msgprint("Please type something");return;}
if(validate_spl_chars(val)){msgprint("Special charaters, commas etc not allowed in tags");return;}
return 1}
TagList.prototype.add_to_locals=function(tag){if(locals[this.dt]&&locals[this.dt][this.dn]){var doc=locals[this.dt][this.dn];if(!doc._user_tags){doc._user_tags=''}
var tl=doc._user_tags.split(',')
tl.push(tag)
doc._user_tags=tl.join(',');}}
TagList.prototype.remove_from_locals=function(tag){if(locals[this.dt]&&locals[this.dt][this.dn]){var doc=locals[this.dt][this.dn];var tl=doc._user_tags.split(',');var new_tl=[];for(var i=0;i<tl.length;i++){if(tl[i]!=tag)new_tl.push(tl[i]);}
doc._user_tags=new_tl.join(',');}}
TagList.prototype.save_tag=function(d){var val=d.get_values();if(val)val=val.tag;var me=this;if(!this.is_text_okay(val))return;var callback=function(r,rt){var d=me.dialog;d.fields_dict.add.input.done_working();d.fields_dict.tag.input.set_input('');d.hide();me.add_to_locals(val)
if(!r.message)return;me.add_tag(r.message,0,'_user_tags');}
me.dialog.fields_dict.add.input.set_working();$c('webnotes.widgets.tags.add_tag',{'dt':me.dt,'dn':me.dn,'tag':val,'color':'na'},callback);}
TagList.prototype.new_tag=function(){var me=this;if(!this.dialog){this.dialog=this.make_tag_dialog();}
this.dialog.show();}
TagList.prototype.refresh_tags=function(){}
function SingleTag(opts){$.extend(this,opts);if(!this.color)this.color='#add8e6';if(this.taglist&&!in_list(this.taglist.tag_list,this.label))
this.taglist.tag_list.push(this.label);this.make_body(this.parent);}
SingleTag.prototype.make_body=function(parent){var me=this;this.body=$a(parent,'span','',{padding:'2px 4px',backgroundColor:this.color,color:'#226',marginRight:'4px'});$br(this.body,'3px');if(this.onclick)$y(this.body,{cursor:'pointer'});$(this.body).hover(function(){$op(this,60);},function(){$op(this,100);});this.make_label();if(!this.static)this.make_remove_btn();_tags.all_tags.push(this);}
SingleTag.prototype.make_remove_btn=function(){var me=this;var span=$a(this.body,'span');span.innerHTML+=' |';var span=$a(this.body,'span','',{cursor:'pointer'});span.innerHTML=' x'
span.onclick=function(){me.remove(me);}}
SingleTag.prototype.make_label=function(){var me=this;this.label_span=$a(this.body,'span','social',null,this.label);this.label_span.onclick=function(){if(me.onclick)me.onclick(me);}}
SingleTag.prototype.remove_tag_body=function(){$dh(this.body);var nl=[];for(var i in this.tag_list)
if(this.tag_list[i]!=this.label)
nl.push(this.tag_list[i]);if(this.taglist)
this.taglist.tag_list=nl;}
SingleTag.prototype.remove=function(){var me=this;var callback=function(r,rt){me.remove_tag_body()
me.taglist.remove_from_locals(me.label);}
$c('webnotes.widgets.tags.remove_tag',{'dt':me.dt,'dn':me.dn,'tag':me.label},callback)
$bg(me.body,'#DDD');}
wn.widgets.TagCloud=function(parent,doctype,onclick){var me=this;this.make=function(r,rt){parent.innerHTML='';if(r.message&&r.message.length){me.tab=make_table(parent,r.message.length,2,'100%',['40px',null],{padding:'5px 3px 5px 0px'})
$y($td(me.tab,0,0),{textAlign:'right'});for(var i=0;i<r.message.length;i++){new wn.widgets.TagCloud.Tag({parent:$td(me.tab,i,1),label:r.message[i][0],onclick:onclick,fieldname:r.message[i][2]},$td(me.tab,i,0),r.message[i])}}else{me.set_no_tags();}
me.refresh=$ln($a(parent,'div'),'refresh',function(){me.refresh.set_working();me.render(1);},{fontSize:'11px',margin:'3px 0px',color:'#888'},1);}
this.set_no_tags=function(){$a(parent,'div','social comment',{fontSize:'11px',margin:'3px 0px'},'<i>No tags yet!, please start tagging</i>');}
this.render=function(refresh){$c('webnotes.widgets.tags.get_top_tags',{doctype:doctype,refresh:(refresh?1:0)},this.make);}
this.render();}
wn.widgets.TagCloud.Tag=function(args,count_cell,det){$(count_cell).css('text-align','right').html(det[1]+' x');args.static=1;this.tag=new SingleTag(args)}
/*
 *	lib/js/legacy/widgets/export_query.js
 */
var export_dialog;function export_query(query,callback){if(!export_dialog){var d=new Dialog(400,300,"Export...");d.make_body([['Data','Max rows','Blank to export all rows'],['Button','Go'],]);d.widgets['Go'].onclick=function(){export_dialog.hide();n=export_dialog.widgets['Max rows'].value;if(cint(n))
export_dialog.query+=' LIMIT 0,'+cint(n);callback(export_dialog.query);}
d.onshow=function(){this.widgets['Max rows'].value='500';}
export_dialog=d;}
export_dialog.query=query;export_dialog.show();}
function export_csv(q,report_name,sc_id,is_simple,filter_values,colnames){var args={}
args.cmd='webnotes.widgets.query_builder.runquery_csv';if(is_simple)
args.simple_query=q;else
args.query=q;args.sc_id=sc_id?sc_id:'';args.filter_values=filter_values?filter_values:'';if(colnames)
args.colnames=colnames.join(',');args.report_name=report_name?report_name:'';open_url_post(outUrl,args);}
/*
 *	lib/js/legacy/webpage/history.js
 */
var nav_obj={}
nav_obj.observers=[];nav_obj.add_observer=function(o){nav_obj.observers.push(o);}
nav_obj.ol=[];nav_obj.open_notify=function(t,dt,dn,no_history){if(nav_obj.ol.length){var tmp=nav_obj.ol[nav_obj.ol.length-1];if(tmp&&tmp[0]==t&&tmp[1]==dt&&tmp[2]==dn)return;}
if(!no_history){var tmp=[];for(var i in nav_obj.ol)
if(!(nav_obj.ol[i][0]==t&&nav_obj.ol[i][1]==dt&&nav_obj.ol[i][2]==dn))tmp.push(nav_obj.ol[i]);nav_obj.ol=tmp;nav_obj.ol.push([t,dt,dn])
en_t=encodeURIComponent(t);en_dt=encodeURIComponent(dt);en_dn=dn?encodeURIComponent(dn):'';if(en_t=='Page'){var id=en_dt+(dn?('/'+en_dn):'')}else{var id=en_t+'/'+en_dt+(dn?('/'+en_dn):'')}
if(nav_obj.on_open)
nav_obj.on_open(id);if(window.location.hash!='!'+id){window.location.hash='!'+id;}}
nav_obj.notify_observers(t,dt,dn);}
nav_obj.notify_observers=function(t,dt,dn){for(var i=0;i<nav_obj.observers.length;i++){var o=nav_obj.observers[i];if(o&&o.notify)o.notify(t,dt,dn);}}
nav_obj.rename_notify=function(dt,oldn,newn){for(var i=0;i<nav_obj.ol.length;i++){var o=nav_obj.ol[i];if(o[1]==dt&&o[2]==oldn)o[2]=newn;}}
nav_obj.show_last_open=function(){var l=nav_obj.ol[nav_obj.ol.length-2];delete nav_obj.ol[nav_obj.ol.length-1];if(!l)loadpage('_home');else if(l[0]=='Page'){loadpage(l[1]);}else if(l[0]=='Report'){loadreport(l[1],l[2]);}else if(l[0]=='Form'){loaddoc(l[1],l[2]);}else if(l[0]=='DocBrowser'||l[0]=='List'){loaddocbrowser(l[1]);}}
var _history_current;function history_get_name(t){var parts=[];if(t.length>=3){for(var i=2;i<t.length;i++){parts.push(t[i]);}}
return parts.join('/')}
nav_obj.get_page=function(loc){if(!loc)loc=window.location.hash;if(loc.substr(0,1)=='#'){loc=loc.substr(1);}
if(loc.substr(0,1)=='!'){loc=loc.substr(1);}
if(!in_list(['Page/','Form/','Repor','DocBr','List/'],loc.substr(0,5))){loc='Page/'+loc;}
return loc.split('/');}
function historyChange(newLocation){var t=nav_obj.get_page(newLocation)
for(var i=0;i<t.length;i++)
t[i]=decodeURIComponent(t[i]);if(nav_obj.ol.length){var c=nav_obj.ol[nav_obj.ol.length-1];if(t.length==2){if(c[0]==t[0]&&c[1]==t[1])return;}else{if(c[0]==t[0]&&c[1]==t[1]&&c[2]==t[2])return;}}
if(t[2])
var docname=history_get_name(t);if(t[0]=='Form'){_history_current=newLocation;if(docname.substr(0,3)=='New'&&!(locals[t[1]]&&locals[t[1]][docname])){newdoc(t[1]);}else{loaddoc(t[1],docname);}}else if(t[0]=='Report'){_history_current=newLocation;loadreport(t[1],docname);}else if(t[0]=='Page'){_history_current=newLocation;loadpage(t[1]);}else if(t[0]=='Application'){_history_current=newLocation;loadapp(t[1]);}else if(t[0]=='DocBrowser'||t[0]=='List'){_history_current=newLocation;loaddocbrowser(t[1]);}};$(window).bind('hashchange',function(){historyChange(location.hash);});
/*
 *	lib/js/legacy/webpage/search.js
 */
search_fields={};function setlinkvalue(name){selector.input.set_input(name);selector.hide();}
function makeselector(){var d=new Dialog(540,440,'Search');d.make_body([['Data','Beginning With','Tip: You can use wildcard "%"'],['Select','Search By'],['Button','Search'],['HTML','Help'],['HTML','Result']]);var inp=d.widgets['Beginning With'];var field_sel=d.widgets['Search By'];var btn=d.widgets['Search'];d.sel_type='';d.values_len=0;d.set=function(input,type,label){d.sel_type=type;d.input=input;if(d.style!='Link'){d.rows['Result'].innerHTML='';d.values_len=0;}
d.style='Link';d.set_query_description()
if(!d.sel_type)d.sel_type='Value';d.set_title('Select a "'+d.sel_type+'" for field "'+label+'"');}
d.set_search=function(dt){if(d.style!='Search'){d.rows['Result'].innerHTML='';d.values_len=0;}
d.style='Search';if(d.input){d.input=null;sel_type=null;}
d.sel_type=get_label_doctype(dt);d.set_title('Quick Search for '+dt);}
inp.onkeydown=function(e){if(isIE)var kc=window.event.keyCode;else var kc=e.keyCode;if(kc==13)if(!btn.disabled)btn.onclick();}
d.set_query_description=function(){if(d.input&&d.input.query_description){d.rows['Help'].innerHTML='<div class="help_box">'+d.input.query_description+'</div>';}else{d.rows['Help'].innerHTML=''}}
d.onshow=function(){if(d.set_doctype!=d.sel_type){d.rows['Result'].innerHTML='';d.values_len=0;}
inp.value='';if(d.input&&d.input.txt.value){inp.value=d.input.txt.value;}
try{inp.focus();}catch(e){}
if(d.input)d.input.set_get_query();var get_sf_list=function(dt){var l=[];var lf=search_fields[dt];for(var i=0;i<lf.length;i++)l.push(lf[i][1]);return l;}
$ds(d.rows['Search By']);if(search_fields[d.sel_type]){empty_select(field_sel);add_sel_options(field_sel,get_sf_list(d.sel_type),'ID');}else{empty_select(field_sel);add_sel_options(field_sel,['ID'],'ID');$c('webnotes.widgets.search.getsearchfields',{'doctype':d.sel_type},function(r,rt){search_fields[d.sel_type]=r.searchfields;empty_select(field_sel);add_sel_options(field_sel,get_sf_list(d.sel_type));field_sel.selectedIndex=0;});}}
d.onhide=function(){if(d.input&&d.input.txt)
d.input.txt.onchange()}
btn.onclick=function(){if(this.disabled)return;this.args.is_ajax=true;this.set_working();d.set_doctype=d.sel_type;var q='';args={};if(d.input&&d.input.get_query){var doc={};args.is_simple=1;if(cur_frm)doc=locals[cur_frm.doctype][cur_frm.docname];var q=d.input.get_query(doc,d.input.doctype,d.input.docname);if(!q){return'';}}
var get_sf_fieldname=function(v){var lf=search_fields[d.sel_type];if(!lf)
return'name'
for(var i=0;i<lf.length;i++)if(lf[i][1]==v)return lf[i][0];}
$.extend(args,{'txt':strip(inp.value),'doctype':d.sel_type,'query':q,'searchfield':get_sf_fieldname(sel_val(field_sel))});$c('webnotes.widgets.search.search_widget',args,function(r,rtxt){btn.done_working();if(r.coltypes)r.coltypes[0]='Link';d.values_len=r.values.length;d.set_result(r);},function(){btn.done_working();});}
d.set_result=function(r){d.rows['Result'].innerHTML='';var c=$a(d.rows['Result'],'div','comment',{paddingBottom:'4px',marginBottom:'4px',borderBottom:'1px solid #CCC',marginLeft:'4px'});if(r.values.length==50)
c.innerHTML='Showing max 50 results. Use filters to narrow down your search';else
c.innerHTML='Showing '+r.values.length+' resuts.';var w=$a(d.rows['Result'],'div','',{height:'240px',overflow:'auto',margin:'4px'});for(var i=0;i<r.values.length;i++){var div=$a(w,'div','',{marginBottom:'4px',paddingBottom:'4px',borderBottom:'1px dashed #CCC'});var l=$a($a(div,'div'),'span','link_type');l.innerHTML=r.values[i][0];l.link_name=r.values[i][0];l.dt=r.coloptions[0];if(d.input)
l.onclick=function(){setlinkvalue(this.link_name);}
else
l.onclick=function(){loaddoc(this.dt,this.link_name);d.hide();}
var cl=[]
for(var j=1;j<r.values[i].length;j++)cl.push(r.values[i][j]);var c=$a(div,'div','comment',{marginTop:'2px'});c.innerHTML=cl.join(', ');}}
selector=d;}
/*
 *	lib/js/legacy/webpage/spinner.js
 */
function set_loading(){pending_req++;$('#spinner').css('visibility','visible');$('body').css('cursor','progress');}
function hide_loading(){pending_req--;if(!pending_req){$('body').css('cursor','default');$('#spinner').css('visibility','hidden');}}
/*
 *	lib/js/legacy/webpage/freeze_page.js
 */
var fcount=0;var frozen=0;var dialog_message;var dialog_back;function freeze(msg,do_freeze){if(!dialog_back){dialog_back=$a($i('body_div'),'div','dialog_back');if(isIE)dialog_back.style['filter']='alpha(opacity=60)';}
$ds(dialog_back);fcount++;frozen=1;}
function unfreeze(){if(dialog_message)
$dh(dialog_message);if(!fcount)return;fcount--;if(!fcount){$dh(dialog_back);frozen=0;}}
/*
 *	lib/js/legacy/webpage/error_console.js
 */
var err_console;var err_list=[];function errprint(t){err_list[err_list.length]=('<pre style="font-family: Courier, Fixed; font-size: 11px; border-bottom: 1px solid #AAA; overflow: auto; width: 90%;">'+t+'</pre>');}
function setup_err_console(){err_console=new Dialog(640,480,'Error Console')
err_console.make_body([['HTML','Error List'],['Button','Clear'],['HTML','Error Report']]);var span=$a(err_console.widgets['Error Report'],'span','link_type');span.innerHTML='Send Error Report';span.onclick=function(){msg=prompt('How / where did you get the error [optional]')
var call_back=function(r,rt){err_console.hide();msgprint("Error Report Sent")}
$c('webnotes.utils.send_error_report',{'err_msg':err_console.rows['Error List'].innerHTML,'msg':msg},call_back);}
err_console.widgets['Clear'].onclick=function(){err_list=[];err_console.rows['Error List'].innerHTML='';err_console.hide();}
err_console.onshow=function(){err_console.rows['Error List'].innerHTML='<div style="padding: 16px; height: 360px; width: 90%; overflow: auto;">'
+err_list.join('<div style="height: 10px; margin-bottom: 10px; border-bottom: 1px solid #AAA"></div>')+'</div>';}}
startup_list.push(setup_err_console);
/*
 *	lib/js/legacy/webpage/loaders.js
 */
function loadreport(dt,rep_name,onload,menuitem,reset_report){wn.require('lib/js/legacy/report.compressed.js');dt=get_label_doctype(dt);var show_report_builder=function(){if(!_r.rb_con){_r.rb_con=new _r.ReportContainer();}
_r.rb_con.set_dt(dt,function(rb){if(rep_name){var t=rb.current_loaded;rb.load_criteria(rep_name);if(onload)
onload(rb);if((rb.dt)&&(!rb.dt.has_data()||rb.current_loaded!=t))
rb.dt.run();}else{if(reset_report){rb.reset_report();}}
if(!rb.forbidden){page_body.change_to('Report Builder');nav_obj.open_notify('Report',dt,rep_name);}});}
show_report_builder();}
var load_doc=loaddoc;function loaddoc(doctype,name,onload,menuitem,from_archive){wn.require('lib/js/legacy/form.compressed.js');doctype=get_label_doctype(doctype);if(frms['DocType']&&frms['DocType'].opendocs[doctype]){msgprint("Cannot open an instance of \""+doctype+"\" when the DocType is open.");return;}
if(doctype=='DocType'&&frms[name]){msgprint("Cannot open DocType \""+name+"\" when its instance is open.");return;}
var show_form=function(f){if(!_f.frm_con){_f.frm_con=new _f.FrmContainer();}
if(!frms[doctype]){_f.add_frm(doctype,show_doc,name,from_archive);}else if(LocalDB.is_doc_loaded(doctype,name)){show_doc();}else{$c('webnotes.widgets.form.load.getdoc',{'name':name,'doctype':doctype,'user':user,'from_archive':(from_archive?1:0)},show_doc,null,null);}}
var show_doc=function(r,rt){if(locals[doctype]&&locals[doctype][name]){page_body.set_status('Done');var frm=frms[doctype];frm.refresh(name);if(!frm.in_dialog)
nav_obj.open_notify('Form',doctype,name);if(onload)onload();}else{if(r.exc){msgprint('There were errors while loading '+doctype+' '+name);}
loadpage('_home');}}
show_form();}
function new_doc(doctype,onload,in_dialog,on_save_callback,cdt,cdn,cnic){wn.require('lib/js/legacy/form.compressed.js');doctype=get_label_doctype(doctype);if(!doctype){if(cur_frm)doctype=cur_frm.doctype;else return;}
var show_doc=function(){frm=frms[doctype];if(frm.perm[0][CREATE]==1){if(frm.meta.issingle){var dn=doctype;LocalDB.set_default_values(locals[doctype][doctype]);}else
var dn=LocalDB.create(doctype);if(onload)onload(dn);if(frm.in_dialog){var fd=_f.frm_dialog;fd.cdt=cdt;fd.cdn=cdn;fd.cnic=cnic;fd.on_save_callback=on_save_callback;}else{nav_obj.open_notify('Form',doctype,dn);}
frm.refresh(dn);}else{msgprint('error:Not Allowed To Create '+doctype+'\nContact your Admin for help');}}
var show_form=function(){if(!_f.frm_con){_f.frm_con=new _f.FrmContainer();}
if(!frms[doctype])
_f.add_frm(doctype,show_doc);else
show_doc(frms[doctype]);}
show_form();}
var newdoc=new_doc;var pscript={};var cur_page;function loadpage(page_name,call_back,no_history){if(page_name=='_home')
page_name=home_page;var fn=function(r,rt){page_body.set_status('Done');if(page_body.pages[page_name]){var p=page_body.pages[page_name]
page_body.change_to(page_name);}else{var p=render_page(page_name);if(!p)return;}
cur_page=page_name;if(call_back)call_back();scroll(0,0);pscript.update_page_history(page_name,no_history)
try{if(pscript['refresh_'+page_name])pscript['refresh_'+page_name]();}catch(e){console.log(e);}}
if(get_local('Page',page_name)||page_body.pages[page_name])
fn();else{args=get_url_dict();args.name=page_name;$c('webnotes.widgets.page.getpage',args,fn);}}
pscript.update_page_history=function(page_name,no_history){var arg=null;var t=null;if(window.location.hash){var t=nav_obj.get_page(window.location.hash)}else if(get_url_arg('page')){var t=nav_obj.get_page(get_url_arg('page'))}
if(t&&t[1]==page_name)arg=t[2];nav_obj.open_notify('Page',page_name,arg,no_history);}
function loadscript(src,call_back){set_loading();var script=$a('head','script');script.type='text/javascript';script.src=src;script.onload=function(){if(call_back)call_back();hide_loading();}
script.onreadystatechange=function(){if(this.readyState=='complete'||this.readyState=='loaded'){hide_loading();call_back();}}}
var doc_browser_page;function loaddocbrowser(dt,label,fields){wn.require('lib/js/legacy/widgets/form/fields.js');wn.require('lib/js/legacy/webpage/docbrowser.js');dt=get_label_doctype(dt);if(!doc_browser_page)
doc_browser_page=new ItemBrowserPage();doc_browser_page.show(dt,label,fields);nav_obj.open_notify('List',dt,'');}
/*
 *	lib/js/legacy/webpage/uploader.js
 */
var uploaders={};var upload_frame_count=0;Uploader=function(parent,args,callback){var id='frame'+upload_frame_count;upload_frame_count++;this.callback=callback;var div=$a(parent,'div');div.innerHTML='<iframe id="'+id+'" name="'+id+'" src="blank.html" \
  style="width:0px; height:0px; border:0px"></iframe>';var div=$a(parent,'div');div.innerHTML='<form method="POST" enctype="multipart/form-data" action="'+outUrl+'" target="'+id+'"></form>';var ul_form=div.childNodes[0];var f_list=[];var inp_fdata=$a_input($a(ul_form,'span'),'file',{name:'filedata'},{marginLeft:'7px'});if(!('cmd'in args)){var inp=$a_input($a(ul_form,'span'),'hidden',{name:'cmd'});inp.value='uploadfile';}
var inp=$a_input($a(ul_form,'span'),'hidden',{name:'uploader_id'});inp.value=id;var inp=$a_input($a(ul_form,'span'),'submit',null,{marginLeft:'7px'});inp.value='Upload';$y(inp,{width:'80px'});for(var key in args){var inp=$a_input($a(ul_form,'span'),'hidden',{name:key});inp.value=args[key];}
uploaders[id]=this;}
function upload_callback(id,fid){uploaders[id].callback(fid);}
/*
 *	lib/js/legacy/webpage/page.js
 */
var pages=[];var stylesheets=[];function Page(page_name,content){var me=this;this.name=page_name;this.trigger=function(event){try{if(pscript[event+'_'+this.name])
pscript[event+'_'+this.name](this.wrapper);}catch(e){console.log(e);}}
this.onshow=function(){set_title(me.doc.title?me.doc.title:me.name);if(!me.onload_complete){me.trigger('onload');me.onload_complete=true;}
me.trigger('onshow');cur_frm=null;}
this.wrapper=page_body.add_page(page_name,this.onshow);this.cont=this.wrapper
if(content)
this.wrapper.innerHTML=content;if(page_name==home_page)
pages['_home']=this;return this;}
function render_page(page_name,menuitem){if(!page_name)return;if((!locals['Page'])||(!locals['Page'][page_name])){loadpage('_home');return;}
var pdoc=locals['Page'][page_name];if(pdoc.style)set_style(pdoc.style)
if(pdoc.stylesheet){set_style(locals.Stylesheet[pdoc.stylesheet].stylesheet);stylesheets.push(pdoc.stylesheet);}
var p=new Page(page_name,pdoc._Page__content?pdoc._Page__content:pdoc.content);var script=pdoc.__script?pdoc.__script:pdoc.script;p.doc=pdoc;if(script){eval(script);}
page_body.change_to(page_name);return p;}
function refresh_page(page_name){var fn=function(r,rt){render_page(page_name)}
$c('webnotes.widgets.page.getpage',{'name':page_name,stylesheets:JSON.stringify(stylesheets)},fn);}
/*
 *	lib/js/legacy/wn/page_layout.js
 */
wn.PageLayout=function(args){$.extend(this,args)
this.wrapper=$a(this.parent,'div');this.wtab=make_table(this.wrapper,1,2,'100%',[this.main_width,this.sidebar_width]);this.main=$a($td(this.wtab,0,0),'div','layout_wrapper');this.sidebar_area=$a($td(this.wtab,0,1),'div');this.head=$a(this.main,'div');this.toolbar_area=$a(this.main,'div');this.body=$a(this.main,'div');this.footer=$a(this.main,'div');if(this.heading){this.page_head=new PageHeader(this.head,this.heading);}}
/*
 *	lib/js/legacy/wn/widgets/page_sidebar.js
 */
wn.widgets.PageSidebar=function(parent,opts){this.opts=opts
this.sections={}
this.wrapper=$a(parent,'div','psidebar-wrapper')
this.refresh=function(){this.wrapper.innerHTML=''
if(this.opts.title)
this.make_head();for(var i=0;i<this.opts.sections.length;i++){var section=this.opts.sections[i];if((section.display&&section.display())||!section.display){this.sections[section.title]=new wn.widgets.PageSidebarSection(this,section);}}
if(this.opts.onrefresh){this.opts.onrefresh(this)}}
this.make_head=function(){this.head=$a(this.wrapper,'div','psidebar-head','',this.opts.title);}
this.refresh();}
wn.widgets.PageSidebarSection=function(sidebar,opts){this.items=[];this.sidebar=sidebar;this.wrapper=$a(sidebar.wrapper,'div','psidebar-section');this.head=$a(this.wrapper,'div','psidebar-section-head','',opts.title);this.body=$a(this.wrapper,'div','psidebar-section-body');$br(this.wrapper,'5px');this.opts=opts;this.make_items=function(){for(var i=0;i<this.opts.items.length;i++){var item=this.opts.items[i];if((item.display&&item.display())||!item.display){var div=$a(this.body,'div','psidebar-section-item');this.make_one_item(item,div);}}}
this.make_one_item=function(item,div){if(item.type.toLowerCase()=='link')
this.items[item.label]=new wn.widgets.PageSidebarLink(this,item,div);else if(item.type.toLowerCase()=='button')
this.items[item.label]=new wn.widgets.PageSidebarButton(this,this.opts.items[i],div);else if(item.type.toLowerCase()=='html')
this.items[item.label]=new wn.widgets.PageSidebarHTML(this,this.opts.items[i],div);}
this.add_icon=function(parent,icon){if(icon.substr(0,3)=='ic-'){var img=$a(parent,'div','wn-icon '+icon,{cssFloat:'left',marginRight:'7px',marginBottom:'-3px'});}else{var img=$a(parent,'img','',{marginRight:'7px',marginBottom:'-3px'});img.src='lib/images/icons/'+icon;}}
this.refresh=function(){this.body.innerHTML='';if(this.opts.render){this.opts.render(this.body);}
else
this.make_items();}
this.refresh();}
wn.widgets.PageSidebarLink=function(section,opts,wrapper){this.wrapper=wrapper;this.section=section;this.opts=opts;var me=this;if(opts.icon){section.add_icon(this.wrapper,opts.icon);}
this.ln=$a(this.wrapper,'span','link_type psidebar-section-link',opts.style,opts.label);this.ln.onclick=function(){me.opts.onclick(me)};}
wn.widgets.PageSidebarButton=function(section,opts,wrapper){this.wrapper=wrapper;this.section=section;this.opts=opts;var me=this;this.btn=$btn(this.wrapper,opts.label,opts.onclick,opts.style,opts.color);}
wn.widgets.PageSidebarHTML=function(section,opts,wrapper){wrapper.innerHTML=opts.content}
/*
 *	lib/js/legacy/wn/widgets/footer.js
 */
wn.widgets.Footer=function(args){$.extend(this,args);this.make=function(){this.wrapper=$a(this.parent,'div','std-footer');this.table=make_table(this.wrapper,1,this.columns,[],{width:100/this.columns+'%'});this.render_items();}
this.render_items=function(){for(var i=0;i<this.items.length;i++){var item=this.items[i];var div=$a($td(this.table,0,item.column),'div','std-footer-item');div.label=$a($a(div,'div'),'span','link_type','',item.label);div.label.onclick=item.onclick;if(item.description){div.description=$a(div,'div','field_description','',item.description);}}}
if(this.items)
this.make();}
/*
 *	lib/js/legacy/model/local_data.js
 */
var locals={'DocType':{}};var fields={};var fields_list={};var LocalDB={};var READ=0;var WRITE=1;var CREATE=2;var SUBMIT=3;var CANCEL=4;var AMEND=5;LocalDB.getchildren=function(child_dt,parent,parentfield,parenttype){var l=[];for(var key in locals[child_dt]){var d=locals[child_dt][key];if((d.parent==parent)&&(d.parentfield==parentfield)){if(parenttype){if(d.parenttype==parenttype)l.push(d);}else{l.push(d);}}}
l.sort(function(a,b){return(cint(a.idx)-cint(b.idx))});return l;}
LocalDB.add=function(dt,dn){if(!locals[dt])locals[dt]={};if(locals[dt][dn])delete locals[dt][dn];locals[dt][dn]={'name':dn,'doctype':dt,'docstatus':0};return locals[dt][dn];}
LocalDB.delete_doc=function(dt,dn){var doc=get_local(dt,dn);for(var ndt in locals){if(locals[ndt]){for(var ndn in locals[ndt]){var doc=locals[ndt][ndn];if(doc&&doc.parenttype==dt&&(doc.parent==dn||doc.__oldparent==dn)){delete locals[ndt][ndn];}}}}
delete locals[dt][dn];}
function get_local(dt,dn){return locals[dt]?locals[dt][dn]:null;}
LocalDB.sync=function(list){if(list._kl)list=expand_doclist(list);for(var i=0;i<list.length;i++){var d=list[i];if(!d.name)
d.name=LocalDB.get_localname(d.doctype);LocalDB.add(d.doctype,d.name);locals[d.doctype][d.name]=d;if(d.doctype=='DocType'){fields_list[d.name]=[];}else if(d.doctype=='DocField'){if(!d.parent){alert('Error: No parent specified for field "'+d.label+'"');}
if(!fields_list[d.parent])fields_list[d.parent]=[];fields_list[d.parent][fields_list[d.parent].length]=d;if(!fields[d.parent])
fields[d.parent]={};if(d.fieldname){fields[d.parent][d.fieldname]=d;}else if(d.label){fields[d.parent][d.label]=d;}}else if(d.doctype=='Event'){if((!d.localname)&&_c.calendar&&(!_c.calendar.has_event[d.name]))
_c.calendar.set_event(d);}
if(d.localname)
notify_rename_observers(d.doctype,d.localname,d.name);}}
local_name_idx={};LocalDB.get_localname=function(doctype){if(!local_name_idx[doctype])local_name_idx[doctype]=1;var n='New '+get_doctype_label(doctype)+' '+local_name_idx[doctype];local_name_idx[doctype]++;return n;}
LocalDB.set_default_values=function(doc){var doctype=doc.doctype;var docfields=fields_list[doctype];if(!docfields){return;}
for(var fid=0;fid<docfields.length;fid++){var f=docfields[fid];if(!in_list(no_value_fields,f.fieldtype)&&doc[f.fieldname]==null){var v=LocalDB.get_default_value(f.fieldname,f.fieldtype,f['default']);if(v)doc[f.fieldname]=v;}}}
LocalDB.is_doc_loaded=function(dt,dn){var exists=false;if(locals[dt]&&locals[dt][dn])exists=true;if(exists&&dt=='DocType'&&!locals[dt][dn].__islocal&&!frms[dt])
exists=false;return exists;}
function check_perm_match(p,dt,dn){if(!dn)return true;var out=false;if(p.match){if(user_defaults[p.match]){for(var i=0;i<user_defaults[p.match].length;i++){if(user_defaults[p.match][i]==locals[dt][dn][p.match]){return true;}}
return false;}else if(!locals[dt][dn][p.match]){return true;}else{return false;}}else{return true;}}
function get_perm(doctype,dn,ignore_submit){var perm=[[0,0],];if(in_list(user_roles,'Administrator'))perm[0][READ]=1;var plist=getchildren('DocPerm',doctype,'permissions','DocType');for(var pidx in plist){var p=plist[pidx];var pl=cint(p.permlevel?p.permlevel:0);if(in_list(user_roles,p.role)){if(check_perm_match(p,doctype,dn)){if(!perm[pl])perm[pl]=[];if(!perm[pl][READ]){if(cint(p.read))perm[pl][READ]=1;else perm[pl][READ]=0;}
if(!perm[pl][WRITE]){if(cint(p.write)){perm[pl][WRITE]=1;perm[pl][READ]=1;}else perm[pl][WRITE]=0;}
if(!perm[pl][CREATE]){if(cint(p.create))perm[pl][CREATE]=1;else perm[pl][CREATE]=0;}
if(!perm[pl][SUBMIT]){if(cint(p.submit))perm[pl][SUBMIT]=1;else perm[pl][SUBMIT]=0;}
if(!perm[pl][CANCEL]){if(cint(p.cancel))perm[pl][CANCEL]=1;else perm[pl][CANCEL]=0;}
if(!perm[pl][AMEND]){if(cint(p.amend))perm[pl][AMEND]=1;else perm[pl][AMEND]=0;}}}}
if((!ignore_submit)&&dn&&locals[doctype][dn].docstatus>0){for(pl in perm)
perm[pl][WRITE]=0;}
return perm;}
LocalDB.create=function(doctype,n){if(!n)n=LocalDB.get_localname(doctype);var doc=LocalDB.add(doctype,n)
doc.__islocal=1;doc.owner=user;LocalDB.set_default_values(doc);return n;}
LocalDB.delete_record=function(dt,dn){var d=locals[dt][dn];if(!d.__islocal)
d.__oldparent=d.parent;d.parent='old_parent:'+d.parent;d.docstatus=2;d.__deleted=1;}
LocalDB.get_default_value=function(fn,ft,df){if(df=='_Login'||df=='__user')
return user;else if(df=='_Full Name')
return user_fullname;else if(ft=='Date'&&(df=='Today'||df=='__today')){return get_today();}
else if(df)
return df;else if(user_defaults[fn])
return user_defaults[fn][0];else if(sys_defaults[fn])
return sys_defaults[fn];}
LocalDB.add_child=function(doc,childtype,parentfield){var n=LocalDB.create(childtype);var d=locals[childtype][n];d.parent=doc.name;d.parentfield=parentfield;d.parenttype=doc.doctype;return d;}
LocalDB.no_copy_list=['amended_from','amendment_date','cancel_reason'];LocalDB.copy=function(dt,dn,from_amend){var newdoc=LocalDB.create(dt);for(var key in locals[dt][dn]){if(key!=='name'&&key.substr(0,2)!='__'){locals[dt][newdoc][key]=locals[dt][dn][key];}
var df=get_field(dt,key);if(df&&((!from_amend&&cint(df.no_copy)==1)||in_list(LocalDB.no_copy_list,df.fieldname))){locals[dt][newdoc][key]='';}}
return locals[dt][newdoc];}
function make_doclist(dt,dn,deleted){var dl=[];dl[0]=locals[dt][dn];for(var ndt in locals){if(locals[ndt]){for(var ndn in locals[ndt]){var doc=locals[ndt][ndn];if(doc&&doc.parenttype==dt&&(doc.parent==dn||(deleted&&doc.__oldparent==dn))){dl[dl.length]=doc;}}}}
return dl;}
var rename_observers=[];function notify_rename_observers(dt,old_name,new_name){try{var old=locals[dt][old_name];old.parent=null;old.__deleted=1;}catch(e){alert("[rename_from_local] No Document for: "+old_name);}
for(var i=0;i<rename_observers.length;i++){if(rename_observers[i])
rename_observers[i].rename_notify(dt,old_name,new_name);}}
var Meta={};var local_dt={};Meta.make_local_dt=function(dt,dn){var dl=make_doclist('DocType',dt);if(!local_dt[dt])local_dt[dt]={};if(!local_dt[dt][dn])local_dt[dt][dn]={};for(var i=0;i<dl.length;i++){var d=dl[i];if(d.doctype=='DocField'){var key=d.fieldname?d.fieldname:d.label;local_dt[dt][dn][key]=copy_dict(d);}}}
Meta.get_field=function(dt,fn,dn){if(dn&&local_dt[dt]&&local_dt[dt][dn]){return local_dt[dt][dn][fn];}else{if(fields[dt])var d=fields[dt][fn];if(d)return d;}
return{};}
Meta.set_field_property=function(fn,key,val,doc){if(!doc&&(cur_frm.doc))doc=cur_frm.doc;try{local_dt[doc.doctype][doc.name][fn][key]=val;refresh_field(fn);}catch(e){alert("Client Script Error: Unknown values for "+doc.name+','+fn+'.'+key+'='+val);}}
function get_doctype_label(dt){if(session.dt_labels&&session.dt_labels[dt])
return session.dt_labels[dt]
else
return dt}
function get_label_doctype(label){if(session.rev_dt_labels&&session.rev_dt_labels[label])
return session.rev_dt_labels[label]
else
return label}
var getchildren=LocalDB.getchildren;var get_field=Meta.get_field;var createLocal=LocalDB.create;
/*
 *	lib/js/legacy/model/doclist.js
 */
function compress_doclist(list){var kl={};var vl=[];var flx={};for(var i=0;i<list.length;i++){var o=list[i];var fl=[];if(!kl[o.doctype]){var tfl=['doctype','name','docstatus','owner','parent','parentfield','parenttype','idx','creation','modified','modified_by','__islocal','__deleted','__newname','__modified','_user_tags'];var fl=['doctype','name','docstatus','owner','parent','parentfield','parenttype','idx','creation','modified','modified_by','__islocal','__deleted','__newname','__modified','_user_tags'];for(key in fields[o.doctype]){if(!in_list(fl,key)&&!in_list(no_value_fields,fields[o.doctype][key].fieldtype)&&!fields[o.doctype][key].no_column){fl[fl.length]=key;tfl[tfl.length]=key}}
flx[o.doctype]=fl;kl[o.doctype]=tfl}
var nl=[];var fl=flx[o.doctype];for(var j=0;j<fl.length;j++){var v=o[fl[j]];nl.push(v);}
vl.push(nl);}
return JSON.stringify({'_vl':vl,'_kl':kl});}
function expand_doclist(docs){var l=[];for(var i=0;i<docs._vl.length;i++)
l[l.length]=zip(docs._kl[docs._vl[i][0]],docs._vl[i]);return l;}
function zip(k,v){var obj={};for(var i=0;i<k.length;i++){obj[k[i]]=v[i];}
return obj;}
function save_doclist(dt,dn,save_action,onsave,onerr){var doc=locals[dt][dn];var doctype=locals['DocType'][dt];var tmplist=[];var doclist=make_doclist(dt,dn,1);var all_clear=true;if(save_action!='Cancel'){for(var n in doclist){var tmp=check_required(doclist[n].doctype,doclist[n].name,doclist[0].doctype);if(doclist[n].docstatus+''!='2'&&all_clear)
all_clear=tmp;}}
var f=frms[dt];if(f&&!all_clear){if(f)f.savingflag=false;return'Error';}
var _save=function(){page_body.set_status('Saving...')
$c('webnotes.widgets.form.save.savedocs',{'docs':compress_doclist(doclist),'docname':dn,'action':save_action,'user':user},function(r,rtxt){if(f){f.savingflag=false;}
if(r.saved){if(onsave)onsave(r);}else{if(onerr)onerr(r);}},function(){if(f){f.savingflag=false;}},0,(f?'Saving...':''));}
if(doc.__islocal&&(doctype&&doctype.autoname&&doctype.autoname.toLowerCase()=='prompt')){var newname=prompt('Enter the name of the new '+dt,'');if(newname){doc.__newname=strip(newname);_save();}else{msgprint('Not Saved');onerr();}}else{_save();}}
function check_required(dt,dn,parent_dt){var doc=locals[dt][dn];if(doc.docstatus>1)return true;var fl=fields_list[dt];if(!fl)return true;var all_clear=true;var errfld=[];for(var i=0;i<fl.length;i++){var key=fl[i].fieldname;var v=doc[key];if(fl[i].reqd&&is_null(v)&&fl[i].fieldname){errfld[errfld.length]=fl[i].label;if(cur_frm){var f=cur_frm.fields_dict[fl[i].fieldname];if(f){if(f.set_as_error)f.set_as_error(1);if(!cur_frm.error_in_section&&f.parent_section){cur_frm.set_section(f.parent_section.sec_id);cur_frm.error_in_section=1;}}}
if(all_clear)all_clear=false;}}
if(errfld.length)msgprint('<b>Mandatory fields required in '+
(doc.parenttype?(fields[doc.parenttype][doc.parentfield].label+' (Table)'):get_doctype_label(doc.doctype))+':</b>\n'+errfld.join('\n'));return all_clear;}
/*
 *	lib/js/legacy/webpage/body.js
 */
function Body(){this.left_sidebar=null;this.right_sidebar=null;this.status_area=null;var me=this;page_body=this;this.no_of_columns=function(){var n=2;if(cint(me&&me.cp&&me.cp.right_sidebar_width))
n=n+1;return n;}
this.ready=function(){$dh('startup_div');$ds('body_div');}
this.setup_page_areas=function(){var n=this.no_of_columns();this.body_table=make_table(this.body,1,n,'100%');$y(this.body_table,{tableLayout:'fixed'});var c=0;this.left_sidebar=$td(this.body_table,0,c);$y(this.left_sidebar,{width:cint(this.cp.left_sidebar_width)+'px'});c++;this.center=$a($td(this.body_table,0,c),'div');c++;if(cint(this.cp.right_sidebar_width)){this.right_sidebar=$td(this.body_table,0,c);$y(this.right_sidebar,{width:cint(this.cp.right_sidebar_width)+'px'})
c++;}
this.center.header=$a(this.center,'div');this.center.body=$a(this.center,'div');this.center.loading=$a(this.center,'div','',{margin:'200px 0px',fontSize:'14px',color:'#999',textAlign:'center'});this.center.loading.innerHTML='Loading...'}
this.setup_sidebar_menu=function(){if(this.left_sidebar&&this.cp.show_sidebar_menu){sidebar_menu=new SidebarMenu();sidebar_menu.make_menu('');}}
this.run_startup_code=function(){wn.require(wn.modules_path+'/startup/startup.css');wn.require(wn.modules_path+'/startup/startup.js');try{if(this.cp.custom_startup_code)
eval(this.cp.custom_startup_code);}catch(e){errprint(e);}}
this.setup=function(){this.cp=wn.control_panel;this.wrapper=$a($i('body_div'),'div');this.body=$a(this.wrapper,'div');if(user_defaults.hide_sidebars){this.cp.left_sidebar_width=null;this.cp.right_sidebar_width=null;}
this.setup_page_areas();if(user=='Guest')user_defaults.hide_webnotes_toolbar=1;if(!cint(user_defaults.hide_webnotes_toolbar)||user=='Administrator'){wn.provide('wn.ui.toolbar');wn.require('lib/js/wn/ui/toolbar.min.js');this.wntoolbar=new wn.ui.toolbar.Toolbar();}
if(this.cp.page_width)$y(this.wrapper,{width:cint(this.cp.page_width)+'px'});}
this.pages={};this.cur_page=null;this.add_page=function(label,onshow,onhide){var c=$a(this.center.body,'div');if(onshow)
c.onshow=onshow;if(onhide)
c.onhide=onhide;this.pages[label]=c;$dh(c);return c;}
this.change_to=function(label){$dh(this.center.loading);if(me.cur_page&&me.pages[label]!=me.cur_page){if(me.cur_page.onhide)
me.cur_page.onhide();$dh(me.cur_page);}
me.cur_page=me.pages[label];me.cur_page_label=label;$(me.cur_page).fadeIn();if(me.cur_page.onshow)
me.cur_page.onshow(me.cur_page);}
this.set_status=function(txt){if(this.status_area)
this.status_area.innerHTML=txt;}
this.set_session_changed=function(){if(this.session_message_set)return;var div=$a($i('body_div').parentNode,'div','',{textAlign:'center',fontSize:'14px',margin:'150px auto'});$dh('body_div');div.innerHTML='This session has been changed. Please <span class="link_type" onclick="window.location.reload()">refresh</span> to continue';this.session_message_set=1;}
this.setup();}
/*
 *	lib/js/legacy/app.js
 */
var popup_cont;var session={};var start_sid=null;if(!wn)var wn={};function startup(){start_sid=get_cookie('sid');popup_cont=$a(document.getElementsByTagName('body')[0],'div');var setup_globals=function(r){wn.boot=r;profile=r.profile;user=r.profile.name;user_fullname=profile.first_name+(r.profile.last_name?(' '+r.profile.last_name):'');user_defaults=profile.defaults;user_roles=profile.roles;user_email=profile.email;profile.start_items=r.start_items;home_page=r.home_page;_p.letter_heads=r.letter_heads;sys_defaults=r.sysdefaults;session.rt=profile.can_read;if(r.ipinfo)session.ipinfo=r.ipinfo;session.dt_labels=r.dt_labels;session.rev_dt_labels={}
_tags.color_map=r.tag_color_map;if(r.dt_labels){for(key in r.dt_labels)session.rev_dt_labels[r.dt_labels[key]]=key;}
wn.control_panel=r.control_panel;}
var setup_history=function(r){rename_observers.push(nav_obj);}
var setup_events=function(){addEvent('keyup',function(ev,target){for(var i in keypress_observers){if(keypress_observers[i])
keypress_observers[i].notify_keypress(ev,ev.keyCode);}});addEvent('click',function(ev,target){for(var i=0;i<click_observers.length;i++){if(click_observers[i])
click_observers[i].notify_click(ev,target);}});if(isIE){$op($i('dialog_back'),60);}}
var callback=function(r,rt){if(r.exc)console.log(r.exc);setup_globals(r);setup_history();setup_events();var a=new Body();page_body.run_startup_code();page_body.setup_sidebar_menu();for(var i=0;i<startup_list.length;i++){startup_list[i]();}
if(get_url_arg('embed')){newdoc(get_url_arg('embed'));return;}
var t=to_open();if(t){historyChange(t);}else if(home_page){loadpage(home_page);}
page_body.ready();}
if(wn.boot){LocalDB.sync(wn.boot.docs);callback(wn.boot,'');if(wn.boot.error_messages)
console.log(wn.boot.error_messages)
if(wn.boot.server_messages)
msgprint(wn.boot.server_messages);}else{if($i('startup_div'))
$c('startup',{},callback,null,1);}}
function to_open(){if(get_url_arg('page'))
return get_url_arg('page');var h=location.hash;if(h){return h.substr(1);}}
function logout(){$c('logout',args={},function(r,rt){if(r.exc){msgprint(r.exc);return;}
redirect_to_login();});}
function redirect_to_login(){if(login_file)
window.location.href=login_file;else{window.location.reload();}}
_p.def_print_style_body="html, body, div, span, td { font-family: Arial, Helvetica; font-size: 12px; }"+"\npre { margin:0; padding:0;}"
_p.def_print_style_other="\n.simpletable, .noborder { border-collapse: collapse; margin-bottom: 10px;}"
+"\n.simpletable td {border: 1pt solid #000; vertical-align: top; padding: 2px; }"
+"\n.noborder td { vertical-align: top; }"
_p.go=function(html){var d=document.createElement('div')
d.innerHTML=html
$(d).printElement();}
_p.preview=function(html){var w=window.open('');w.document.write(html)
w.document.close();}
function setup_calendar(){var p=new Page('_calendar');p.wrapper.style.height='100%';p.wrapper.onshow=function(){wn.require('lib/js/legacy/widgets/calendar.js');if(!_c.calendar){_c.calendar=new Calendar();_c.calendar.init(p.cont);rename_observers.push(_c.calendar);}}}
startup_list.push(setup_calendar);if(isIE6){var scroll_list=[]
window.onscroll=function(){for(var i=0;i<scroll_list.length;i++){scroll_list[i]();}}}
var resize_observers=[]
function set_resize_observer(fn){if(resize_observers.indexOf(fn)==-1)resize_observers.push(fn);}
window.onresize=function(){return;var ht=get_window_height();for(var i=0;i<resize_observers.length;i++){resize_observers[i](ht);}}
get_window_height=function(){var ht=window.innerHeight?window.innerHeight:document.documentElement.offsetHeight?document.documentElement.offsetHeight:document.body.offsetHeight;return ht;}