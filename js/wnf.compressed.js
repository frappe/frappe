
window.dhtmlHistory={isIE:false,isOpera:false,isSafari:false,isKonquerer:false,isGecko:false,isSupported:false,create:function(_1){var _2=this;var UA=navigator.userAgent.toLowerCase();var _4=navigator.platform.toLowerCase();var _5=navigator.vendor||"";if(_5==="KDE"){this.isKonqueror=true;this.isSupported=false;}else{if(typeof window.opera!=="undefined"){this.isOpera=true;this.isSupported=true;}else{if(typeof document.all!=="undefined"){this.isIE=true;this.isSupported=true;}else{if(_5.indexOf("Apple Computer, Inc.")>-1&&parseFloat(navigator.appVersion)<3.0){this.isSafari=true;this.isSupported=(_4.indexOf("mac")>-1);}else{if(UA.indexOf("gecko")!=-1){this.isGecko=true;this.isSupported=true;}}}}}window.historyStorage.setup(_1);if(this.isSafari){this.createSafari();}else{if(this.isOpera){this.createOpera();}}var _6=this.getCurrentLocation();this.currentLocation=_6;if(this.isIE){this.createIE(_6);}var _7=function(){_2.firstLoad=null;};this.addEventListener(window,"unload",_7);if(this.isIE){this.ignoreLocationChange=true;}else{if(!historyStorage.hasKey(this.PAGELOADEDSTRING)){this.ignoreLocationChange=true;this.firstLoad=true;historyStorage.put(this.PAGELOADEDSTRING,true);}else{this.ignoreLocationChange=false;this.fireOnNewListener=true;}}var _8=function(){_2.checkLocation();};setInterval(_8,100);},initialize:function(){if(this.isIE){if(!historyStorage.hasKey(this.PAGELOADEDSTRING)){this.fireOnNewListener=false;this.firstLoad=true;historyStorage.put(this.PAGELOADEDSTRING,true);}else{this.fireOnNewListener=true;this.firstLoad=false;}}},addListener:function(_9){this.listener=_9;if(this.fireOnNewListener){this.fireHistoryEvent(this.currentLocation);this.fireOnNewListener=false;}},addEventListener:function(o,e,l){if(o.addEventListener){o.addEventListener(e,l,false);}else{if(o.attachEvent){o.attachEvent("on"+e,function(){l(window.event);});}}},add:function(_d,_e){if(this.isSafari){_d=this.removeHash(_d);historyStorage.put(_d,_e);this.currentLocation=_d;window.location.hash=_d;this.putSafariState(_d);}else{var _f=this;var _10=function(){if(_f.currentWaitTime>0){_f.currentWaitTime=_f.currentWaitTime-_f.waitTime;}_d=_f.removeHash(_d);if(document.getElementById(_d)&&_f.debugMode){var e="Exception: History locations can not have the same value as _any_ IDs that might be in the document,"+" due to a bug in IE; please ask the developer to choose a history location that does not match any HTML"+" IDs in this document. The following ID is already taken and cannot be a location: "+_d;throw new Error(e);}historyStorage.put(_d,_e);_f.ignoreLocationChange=true;_f.ieAtomicLocationChange=true;_f.currentLocation=_d;window.location.hash=_d;if(_f.isIE){_f.iframe.src="blank.html?"+_d;}_f.ieAtomicLocationChange=false;};window.setTimeout(_10,this.currentWaitTime);this.currentWaitTime=this.currentWaitTime+this.waitTime;}},isFirstLoad:function(){return this.firstLoad;},getVersion:function(){return"0.6";},getCurrentLocation:function(){var r=(this.isSafari?this.getSafariState():this.getCurrentHash());return r;},getCurrentHash:function(){var r=window.location.href;var i=r.indexOf("#");return(i>=0?r.substr(i+1):"");},PAGELOADEDSTRING:"DhtmlHistory_pageLoaded",listener:null,waitTime:200,currentWaitTime:0,currentLocation:null,iframe:null,safariHistoryStartPoint:null,safariStack:null,safariLength:null,ignoreLocationChange:null,fireOnNewListener:null,firstLoad:null,ieAtomicLocationChange:null,createIE:function(_15){this.waitTime=400;var _16=(historyStorage.debugMode?"width: 800px;height:80px;border:1px solid black;":historyStorage.hideStyles);var _17="rshHistoryFrame";var _18="<iframe frameborder=\"0\" id=\""+_17+"\" style=\""+_16+"\" src=\"blank.html?"+_15+"\"></iframe>";document.write(_18);this.iframe=document.getElementById(_17);},createOpera:function(){this.waitTime=400;var _19="<img src=\"javascript:location.href='javascript:dhtmlHistory.checkLocation();';\" style=\""+historyStorage.hideStyles+"\" />";document.write(_19);},createSafari:function(){var _1a="rshSafariForm";var _1b="rshSafariStack";var _1c="rshSafariLength";var _1d=historyStorage.debugMode?historyStorage.showStyles:historyStorage.hideStyles;var _1e=(historyStorage.debugMode?"width:800px;height:20px;border:1px solid black;margin:0;padding:0;":historyStorage.hideStyles);var _1f="<form id=\""+_1a+"\" style=\""+_1d+"\">"+"<input type=\"text\" style=\""+_1e+"\" id=\""+_1b+"\" value=\"[]\"/>"+"<input type=\"text\" style=\""+_1e+"\" id=\""+_1c+"\" value=\"\"/>"+"</form>";document.write(_1f);this.safariStack=document.getElementById(_1b);this.safariLength=document.getElementById(_1c);if(!historyStorage.hasKey(this.PAGELOADEDSTRING)){this.safariHistoryStartPoint=history.length;this.safariLength.value=this.safariHistoryStartPoint;}else{this.safariHistoryStartPoint=this.safariLength.value;}},getSafariStack:function(){var r=this.safariStack.value;return historyStorage.fromJSON(r);},getSafariState:function(){var _21=this.getSafariStack();var _22=_21[history.length-this.safariHistoryStartPoint-1];return _22;},putSafariState:function(_23){var _24=this.getSafariStack();_24[history.length-this.safariHistoryStartPoint]=_23;this.safariStack.value=historyStorage.toJSON(_24);},fireHistoryEvent:function(_25){var _26=historyStorage.get(_25);this.listener.call(null,_25,_26);},checkLocation:function(){if(!this.isIE&&this.ignoreLocationChange){this.ignoreLocationChange=false;return;}if(!this.isIE&&this.ieAtomicLocationChange){return;}var _27=this.getCurrentLocation();if(_27==this.currentLocation){return;}this.ieAtomicLocationChange=true;if(this.isIE&&this.getIframeHash()!=_27){this.iframe.src="blank.html?"+_27;}else{if(this.isIE){return;}}this.currentLocation=_27;this.ieAtomicLocationChange=false;this.fireHistoryEvent(_27);},getIframeHash:function(){var doc=this.iframe.contentWindow.document;var _29=String(doc.location.search);if(_29.length==1&&_29.charAt(0)=="?"){_29="";}else{if(_29.length>=2&&_29.charAt(0)=="?"){_29=_29.substring(1);}}return _29;},removeHash:function(_2a){var r;if(_2a===null||_2a===undefined){r=null;}else{if(_2a===""){r="";}else{if(_2a.length==1&&_2a.charAt(0)=="#"){r="";}else{if(_2a.length>1&&_2a.charAt(0)=="#"){r=_2a.substring(1);}else{r=_2a;}}}}return r;},iframeLoaded:function(_2c){if(this.ignoreLocationChange){this.ignoreLocationChange=false;return;}var _2d=String(_2c.search);if(_2d.length==1&&_2d.charAt(0)=="?"){_2d="";}else{if(_2d.length>=2&&_2d.charAt(0)=="?"){_2d=_2d.substring(1);}}window.location.hash=_2d;this.fireHistoryEvent(_2d);}};window.historyStorage={setup:function(_2e){if(typeof _2e!=="undefined"){if(_2e.debugMode){this.debugMode=_2e.debugMode;}if(_2e.toJSON){this.toJSON=_2e.toJSON;}if(_2e.fromJSON){this.fromJSON=_2e.fromJSON;}}var _2f="rshStorageForm";var _30="rshStorageField";var _31=this.debugMode?historyStorage.showStyles:historyStorage.hideStyles;var _32=(historyStorage.debugMode?"width: 800px;height:80px;border:1px solid black;":historyStorage.hideStyles);var _33="<form id=\""+_2f+"\" style=\""+_31+"\">"+"<textarea id=\""+_30+"\" style=\""+_32+"\"></textarea>"+"</form>";document.write(_33);this.storageField=document.getElementById(_30);if(typeof window.opera!=="undefined"){this.storageField.focus();}},put:function(key,_35){this.assertValidKey(key);if(this.hasKey(key)){this.remove(key);}this.storageHash[key]=_35;this.saveHashTable();},get:function(key){this.assertValidKey(key);this.loadHashTable();var _37=this.storageHash[key];if(_37===undefined){_37=null;}return _37;},remove:function(key){this.assertValidKey(key);this.loadHashTable();delete this.storageHash[key];this.saveHashTable();},reset:function(){this.storageField.value="";this.storageHash={};},hasKey:function(key){this.assertValidKey(key);this.loadHashTable();return(typeof this.storageHash[key]!=="undefined");},isValidKey:function(key){return(typeof key==="string");},showStyles:"border:0;margin:0;padding:0;",hideStyles:"left:-1000px;top:-1000px;width:1px;height:1px;border:0;position:absolute;",debugMode:false,storageHash:{},hashLoaded:false,storageField:null,assertValidKey:function(key){var _3c=this.isValidKey(key);if(!_3c&&this.debugMode){throw new Error("Please provide a valid key for window.historyStorage. Invalid key = "+key+".");}},loadHashTable:function(){if(!this.hashLoaded){var _3d=this.storageField.value;if(_3d!==""&&_3d!==null){this.storageHash=this.fromJSON(_3d);this.hashLoaded=true;}}},saveHashTable:function(){this.loadHashTable();var _3e=this.toJSON(this.storageHash);this.storageField.value=_3e;},toJSON:function(o){return o;},fromJSON:function(s){return s;}};var wn={}
wn.widgets={form:{},report:{}}
wn.utils={}
wn.model={}
wn.profile={}
wn.session={}
var NEWLINE='\n';var login_file='';var version='v170';var profile;var session={};var is_testing=false;var user;var user_defaults;var user_roles;var user_fullname;var user_email;var user_img={};var home_page;var page_body;var pscript={};var selector;var keypress_observers=[];var click_observers=[];var editAreaLoader;var top_index=91;var _f={};var _p={};var _e={};var _r={};var FILTER_SEP='\1';var _c={};var widget_files={'_f.FrmContainer':'form.compressed.js','_c.CalendarPopup':'widgets/form/date_picker.js','_r.ReportContainer':'report.compressed.js','_p.PrintQuery':'widgets/print_query.js','Calendar':'widgets/calendar.js','Recommendation':'widgets/recommend.js','RatingWidget':'widgets/rating.js'}
var Recommendation;var RatingWidget;var frms={};var cur_frm;var pscript={};var validated=true;var validation_message='';var tinymce_loaded;var $c_get_values;var get_server_fields;var set_multiple;var set_field_tip;var refresh_field;var refresh_many;var set_field_options;var set_field_permlevel;var hide_field;var unhide_field;var print_table;var sendmail;var exp_icon="images/ui/right-arrow.gif";var min_icon="images/ui/down-arrow.gif";var space_holder_div=$a(null,'div','space_holder');space_holder_div.innerHTML='Loading...'
var startup_list=[];wn.utils.full_name=function(fn,ln){return fn+(ln?' ':'')+(ln?ln:'')}
function fmt_money(v){if(v==null||v=='')return'0.00';v=(v+'').replace(/,/g,'');v=parseFloat(v);if(isNaN(v)){return'';}else{var cp=locals['Control Panel']['Control Panel'];var val=2;if(cp.currency_format=='Millions')val=3;v=v.toFixed(2);var delimiter=",";amount=v+'';var a=amount.split('.',2)
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
ele.innerHTML=fmt_money(v);}else if(ftype=='Int'){ele.style.textAlign='right';ele.innerHTML=v;}else if(ftype=='Check'){if(v)ele.innerHTML='<img src="images/ui/tick.gif">';else ele.innerHTML='';}else{ele.innerHTML=v;}}
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
function seval(s){return eval('var a='+s+';a');}
function in_list(list,item){for(var i=0;i<list.length;i++)
if(list[i]==item)return true;return false;}
function has_common(list1,list2){if(!list1||!list2)return false;for(var i=0;i<list1.length;i++){if(in_list(list2,list1[i]))return true;}
return false;}
var inList=in_list;function add_lists(l1,l2){var l=[];for(var k in l1)l.push(l1[k]);for(var k in l2)l.push(l2[k]);return l;}
function docstring(obj){var l=[];for(key in obj){var v=obj[key];if(v!=null){if(typeof(v)==typeof(1)){l[l.length]="'"+key+"':"+(v+'');}else{v=v+'';l[l.length]="'"+key+"':'"+v.replace(/'/g,"\\'").replace(/\n/g,"\\n")+"'";}}}
return"{"+l.join(',')+'}';}
function ie_refresh(e){$dh(e);$ds(e);}
function DocLink(p,doctype,name,onload){var a=$a(p,'span','link_type');a.innerHTML=a.dn=name;a.dt=doctype;a.onclick=function(){loaddoc(this.dt,this.dn,onload)};return a;}
var doc_link=DocLink;var known_numbers={0:'zero',1:'one',2:'two',3:'three',4:'four',5:'five',6:'six',7:'seven',8:'eight',9:'nine',10:'ten',11:'eleven',12:'twelve',13:'thirteen',14:'fourteen',15:'fifteen',16:'sixteen',17:'seventeen',18:'eighteen',19:'nineteen',20:'twenty',30:'thirty',40:'forty',50:'fifty',60:'sixty',70:'seventy',80:'eighty',90:'ninety'}
function in_words(n){var is_million=locals['Control Panel']['Control Panel'].currency_format=='Millions'?1:0;n=cint(n)
if(known_numbers[n])return known_numbers[n];var bestguess=n+'';var remainder=0
if(n<=20)
alert('Error while converting to words');else if(n<100){return in_words(Math.floor(n/10)*10)+'-'+in_words(n%10);}else if(n<1000){bestguess=in_words(Math.floor(n/100))+' '+'hundred';remainder=n%100;}else if(!is_million){if(n<100000){bestguess=in_words(Math.floor(n/1000))+' '+'thousand';remainder=n%1000;}else if(n<10000000){bestguess=in_words(Math.floor(n/100000))+' '+'lakh';remainder=n%100000;}else{bestguess=in_words(Math.floor(n/10000000))+' '+'crore'
remainder=n%10000000}}else{if(n<1000000){bestguess=in_words(Math.floor(n/1000))+' '+'thousand';remainder=n%1000;}else if(n<1000000000){bestguess=in_words(Math.floor(n/1000000))+' '+'million';remainder=n%1000000;}else{bestguess=in_words(Math.floor(n/1000000000))+' '+'billion'
remainder=n%1000000000}}
if(remainder){if(remainder>=100)comma=','
else comma=''
return bestguess+comma+' '+in_words(remainder);}else{return bestguess;}}
var appVer=navigator.appVersion.toLowerCase();var is_minor=parseFloat(appVer);var is_major=parseInt(is_minor);var iePos=appVer.indexOf('msie');if(iePos!=-1){is_minor=parseFloat(appVer.substring(iePos+5,appVer.indexOf(';',iePos)))
is_major=parseInt(is_minor);}
var isIE=(iePos!=-1);var isIE6=(isIE&&is_major<=6);var isIE7=(isIE&&is_major>=7);if(/Firefox[\/\s](\d+\.\d+)/.test(navigator.userAgent)){var isFF=1;var ffversion=new Number(RegExp.$1)
if(ffversion>=3)var isFF3=1;else if(ffversion>=2)var isFF2=1;else if(ffversion>=1)var isFF1=1;}
var isSafari=navigator.userAgent.indexOf('Safari')!=-1?1:0;var isChrome=navigator.userAgent.indexOf('Chrome')!=-1?1:0;function same_day(d1,d2){if(d1.getFullYear()==d2.getFullYear()&&d1.getMonth()==d2.getMonth()&&d1.getDate()==d2.getDate())return true;else return false;}
var month_list=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];var month_last={1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31}
var month_list_full=['January','February','March','April','May','June','July','August','September','October','November','December'];var week_list=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];var week_list_full=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];function int_to_str(i,len){i=''+i;if(i.length<len)for(c=0;c<(len-i.length);c++)i='0'+i;return i}
wn.datetime={str_to_obj:function(d){if(!d)return new Date();var tm=[null,null];if(d.search(' ')!=-1){var tm=d.split(' ')[1].split(':');var d=d.split(' ')[0];}
if(d.search('-')!=-1){var t=d.split('-');return new Date(t[0],t[1]-1,t[2],tm[0],tm[1]);}else if(d.search('/')!=-1){var t=d.split('/');return new Date(t[0],t[1]-1,t[2],tm[0],tm[1]);}else{return new Date();}},obj_to_str:function(d){return d.getFullYear()+'-'+int_to_str(d.getMonth()+1,2)+'-'+int_to_str(d.getDate(),2);},obj_to_user:function(d){return dateutil.str_to_user(dateutil.obj_to_str(d));},get_diff:function(d1,d2){return((d1-d2)/86400000);},add_days:function(d,days){d.setTime(d.getTime()+(days*24*60*60*1000));return d},add_months:function(d,months){dt=dateutil.str_to_obj(d)
new_dt=new Date(dt.getFullYear(),dt.getMonth()+months,dt.getDate())
if(new_dt.getDate()!=dt.getDate()){return dateutil.month_end(new Date(dt.getFullYear(),dt.getMonth()+months,1))}
return dateutil.obj_to_str(new_dt);},month_start:function(){var d=new Date();return d.getFullYear()+'-'+int_to_str(d.getMonth()+1,2)+'-01';},month_end:function(d){if(!d)var d=new Date();var m=d.getMonth()+1;var y=d.getFullYear();last_date=month_last[m];if(m==2&&(y%4)==0&&((y%100)!=0||(y%400)==0))
last_date=29;return y+'-'+int_to_str(m,2)+'-'+last_date;},get_user_fmt:function(){var t=locals['Control Panel']['Control Panel'].date_format;if(!t)t='dd-mm-yyyy';return t;},str_to_user:function(val,no_time_str){var user_fmt=dateutil.get_user_fmt();var time_str='';if(val==null||val=='')return null;if(val.search(':')!=-1){var tmp=val.split(' ');if(tmp[1])
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
wn.datetime.comment_when=function(dt,only_days){if(only_days){var cdate=dateutil.str_to_obj(dt.split(' ')[0]);var diff=(new Date()-cdate)/1000;if(diff<604800){var t=Math.floor(diff/86400);if(t==0)return"Today";if(t==1)return"Yesterday";return t+" days ago"}else{return cdate.getDate()+" "+month_list[cdate.getMonth()]+" "+cdate.getFullYear();}}else{var cdate=dateutil.str_to_obj(dt);var diff=(new Date()-cdate)/1000;if(diff<60){return"Few moments ago"}else if(diff<3600){var t=Math.floor(diff/60);return t+" minute"+(t==1?"":"s")+" ago"}else if(diff<86400){var t=Math.floor(diff/3600);return t+" hour"+(t==1?"":"s")+" ago"}else if(diff<604800){var t=Math.floor(diff/86400);return t+" day"+(t==1?"":"s")+" ago"}else{return cdate.getDate()+" "+month_list[cdate.getMonth()]+" "+cdate.getFullYear();}}}
var date=dateutil=wn.datetime;var get_today=wn.datetime.get_today
var comment_when=wn.datetime.comment_when;var time_to_ampm=wn.datetime.time_to_ampm;var time_to_hhmm=wn.datetime.time_to_hhmm;var only_date=wn.datetime.only_date;wn.dom={id_count:0,set_unique_id:function(ele){var id='unique-'+wn.dom.id_count;ele.setAttribute('id',id);wn.dom.id_count++;return id;}}
wn.tinymce={add_simple:function(ele,height){if(ele.myid){tinyMCE.execCommand('mceAddControl',true,ele.myid);return;}
ele.myid=wn.dom.set_unique_id(ele);$(ele).tinymce({script_url:'js/tiny_mce_33/tiny_mce.js',height:height?height:'200px',theme:"advanced",theme_advanced_buttons1:"bold,italic,underline,separator,strikethrough,justifyleft,justifycenter,justifyright,justifyfull,bullist,numlist,outdent,indent,link,unlink,forecolor,backcolor,code,",theme_advanced_buttons2:"",theme_advanced_buttons3:"",theme_advanced_toolbar_location:"top",theme_advanced_toolbar_align:"left",theme_advanced_path:false,theme_advanced_resizing:false});},remove:function(ele){tinyMCE.execCommand('mceRemoveControl',true,ele.myid);},get_value:function(ele){return tinymce.get(ele.myid).getContent();}}
wn.ele={link:function(args){var span=$a(args.parent,'span','link_type',args.style);span.loading_img=$a(args.parent,'img','',{margin:'0px 4px -2px 4px',display:'none'});span.loading_img.src='images/ui/button-load.gif';span.innerHTML=args.label;span.user_onclick=args.onclick;span.onclick=function(){if(!this.disabled)this.user_onclick(this);}
span.set_working=function(){this.disabled=1;$di(this.loading_img);}
span.done_working=function(){this.disabled=0;$dh(this.loading_img);}
return span;},button:function(args){var btn=$a(args.parent,'button');btn.loading_img=$a(args.parent,'img','',{margin:'0px 4px -2px 4px',display:'none'});btn.loading_img.src='images/ui/button-load.gif';$wid_make(btn,color);if(args.is_ajax)$y(btn,{marginRight:'24px'});btn.innerHTML=args.label;btn.user_onclick=args.onclick;btn.color=args.color;btn.onclick=function(){if(!this.disabled)this.user_onclick(this);}
$(btn).hover(function(){$wid_active(this);},function(){$wid_normal(this);})
btn.onmousedown=function(){$wid_pressed(this);}
btn.onmouseup=function(){$wid_active(this);}
btn.set_disabled=function(){$wid_disabled(this);}
btn.set_enabled=function(){this.disabled=0;$wid_normal(this);}
btn.set_working=function(){this.set_disabled();$di(this.loading_img);if(args.is_ajax)$y(btn,{marginRight:'0px'});}
btn.done_working=function(){this.set_enabled();$dh(this.loading_img);if(args.is_ajax)$y(btn,{marginRight:'24px'});}
if(args.style)$y(btn,args.style);return btn;}}
function $ln(parent,label,onclick,style){return wn.ele.link({parent:parent,label:label,onclick:onclick,style:style})}
function $btn(parent,label,onclick,style,color,is_ajax){return wn.ele.button({parent:parent,label:label,onclick:onclick,style:style,is_ajax:is_ajax})}
function addEvent(ev,fn){if(isIE){document.attachEvent('on'+ev,function(){fn(window.event,window.event.srcElement);});}else{document.addEventListener(ev,function(e){fn(e,e.target);},true);}}
$wid_normal=function(ele){if(ele.disabled)return;$y(ele,{border:'1px solid #AAC',color:'#446'});$gr(ele,'#FFF','#D8D8E2');if(ele.no_left_border)$y(ele,{borderLeft:'0px'})
if(ele.wid_color=='green'){$y(ele,{color:'#FFF',border:'1px solid #4B4'});$gr(ele,'#9C9','#4A4');}}
$wid_make=function(ele,color){if(ele.disabled)return;fsize=ele.style.fontSize?ele.style.fontSize:'11px';$y(ele,{padding:'2px 8px',cursor:'pointer',fontSize:fsize});$br(ele,'2px');$bs(ele,'0.5px 0.5px 2px #EEE');ele.wid_color=color?color:'normal';$wid_normal(ele);}
$wid_disabled=function(ele){ele.disabled=1;$y(ele,{border:'1px solid #AAA'});$bg(ele,'#E8E8EA');$fg(ele,'#AAA');}
$wid_active=function(ele){if(ele.disabled)return;$y(ele,{border:'1px solid #446',color:'#446'});$gr(ele,'#FFF','#EEF');if(ele.no_left_border)$y(ele,{borderLeft:'0px'})
if(ele.wid_color=='green'){$y(ele,{color:'#FFF',border:'1px solid #292'});$gr(ele,'#AFA','#7C7');}}
$wid_pressed=function(ele){if(ele.disabled)return;$y(ele,{border:'1px solid #444'});$gr(ele,'#EEF','#DDF');if(ele.wid_color=='green'){$y(ele,{color:'#FFF',border:'1px solid #292'});$gr(ele,'#7C7','#2A2');}}
$item_normal=function(ele){$y(ele,{padding:'6px 8px',cursor:'pointer',marginRight:'8px',whiteSpace:'nowrap',overflow:'hidden',borderBottom:'1px solid #DDD'});$bg(ele,'#FFF');$fg(ele,'#000');}
$item_active=function(ele){$bg(ele,'#FE8');$fg(ele,'#000');}
$item_selected=function(ele){$bg(ele,'#777');$fg(ele,'#FFF');}
$item_pressed=function(ele){$bg(ele,'#F90');$fg(ele,'#FFF');}
$item_set_working=function(ele){if(ele.loading_img){$di(ele.loading_img)}else{ele.disabled=1;ele.loading_img=$a(ele.parentNode,'img','',{marginLeft:'4px',marginBottom:'-2px',display:'inline'});ele.loading_img.src='images/ui/button-load.gif';}}
$item_done_working=function(ele){ele.disabled=0;if(ele.loading_img){$dh(ele.loading_img)};}
function set_opacity(ele,ieop){var op=ieop/100;if(ele.filters){try{ele.filters.item("DXImageTransform.Microsoft.Alpha").opacity=ieop;}catch(e){ele.style.filter='progid:DXImageTransform.Microsoft.Alpha(opacity='+ieop+')';}}else{ele.style.opacity=op;}}
function $btn_join(btn1,btn2){$br(btn1,'0px',[0,1,1,0]);$br(btn2,'0px',[1,0,0,1]);$y(btn1,{marginRight:'0px'});$y(btn2,{marginLeft:'0px',borderLeft:'0px'});btn2.no_left_border=1;}
function set_gradient(ele,from,to){var no_gradient=0;if(isIE)no_gradient=1;if(isFF&&ffversion<3.6)no_gradient=1;if(no_gradient){var rgb_from=get_rgb(from.substr(1));var rgb_to=get_rgb(to.substr(1));$y(ele,{backgroundColor:'#'
+d2h(rgb_to[0]+(rgb_from[0]-rgb_to[0])/2)
+d2h(rgb_to[1]+(rgb_from[1]-rgb_to[1])/2)
+d2h(rgb_to[2]+(rgb_from[2]-rgb_to[2])/2)});}else{$y(ele,{background:'-webkit-gradient(linear, left top, left bottom, from('+from+'), to('+to+'))'});$y(ele,{background:'-moz-linear-gradient(top, '+from+', '+to+')'});}}
$gr=set_gradient;$br=function(ele,r,corners){if(corners){var cl=['top-left','top-right','bottom-right','bottom-left'];for(var i=0;i<4;i++){if(corners[i]){$(ele).css('-moz-border-radius-'+cl[i].replace('-',''),r).css('-webkit-'+cl[i]+'-border-radius',r);}}}else{$(ele).css('-moz-border-radius',r).css('-webkit-border-radius',r).css('border-radius',r);}}
$bs=function(ele,r){$(ele).css('-moz-box-shadow',r).css('-webkit-box-shadow',r).css('box-shadow',r);}
function $btn(parent,label,onclick,style,color,ajax){var btn=$a(parent,'button');btn.loading_img=$a(parent,'img','',{margin:'0px 4px -2px 4px',display:'none'});btn.loading_img.src='images/ui/button-load.gif';$wid_make(btn,color);if(ajax)$y(btn,{marginRight:'24px'});btn.innerHTML=label;btn.user_onclick=onclick;btn.color=color;btn.onclick=function(){if(!this.disabled)this.user_onclick(this);}
$(btn).hover(function(){$wid_active(this);},function(){$wid_normal(this);})
btn.onmousedown=function(){$wid_pressed(this);}
btn.onmouseup=function(){$wid_active(this);}
btn.set_disabled=function(){$wid_disabled(this);}
btn.set_enabled=function(){this.disabled=0;$wid_normal(this);}
btn.set_working=function(){this.set_disabled();$di(this.loading_img);if(ajax)$y(btn,{marginRight:'0px'});}
btn.done_working=function(){this.set_enabled();$dh(this.loading_img);if(ajax)$y(btn,{marginRight:'24px'});}
if(style)$y(btn,style);return btn;}
(function($){$.fn.add_default_text=function(txt){return this.each(function(){$(this).attr('default_text',txt).bind('focus',function(){if(this.value==$(this).attr('default_text')){$(this).val('').css('color','#000');}}).bind('blur',function(){if(!this.value){$(this).val($(this).attr('default_text')).css('color','#888');}}).blur();});};})(jQuery);function empty_select(s){if(s.custom_select){s.empty();return;}
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
function get_darker_shade(col,factor){if(!factor)factor=0.5;rgb=get_rgb(col)
return""+d2h(cint(rgb[0]*factor))+d2h(cint(rgb[1]*factor))+d2h(cint(rgb[2]*factor));}
function get_rgb(col){if(col.length==3){return[h2d(col[0]),h2d(col[1]),h2d(col[2])]}
else if(col.length==6){return[h2d(col.substr(0,2)),h2d(col.substr(2,2)),h2d(col.substr(4,2))]}
else return[];}
var $n='\n';var $f_lab='<div style="padding: 4px; color: #888;">Fetching...</div>';var my_title='Home';var title_prefix='';function set_title(t){document.title=(title_prefix?(title_prefix+' - '):'')+t;}
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
function get_page_size(){if(window.innerHeight&&window.scrollMaxY){yh=window.innerHeight+window.scrollMaxY;xh=window.innerWidth+window.scrollMaxX;}else if(document.body.scrollHeight>document.body.offsetHeight){yh=document.body.scrollHeight;xh=document.body.scrollWidth;}else{yh=document.body.offsetHeight;xh=document.body.offsetWidth;}
r=[xh,yh];return r;}
function get_scroll_top(){var st=0;if(document.documentElement&&document.documentElement.scrollTop)
st=document.documentElement.scrollTop;else if(document.body&&document.body.scrollTop)
st=document.body.scrollTop;return st;}
function get_cookie(c){var t=""+document.cookie;var ind=t.indexOf(c);if(ind==-1||c=="")return"";var ind1=t.indexOf(';',ind);if(ind1==-1)ind1=t.length;return unescape(t.substring(ind+c.length+1,ind1));}
add_space_holder=function(parent,cs){if(!cs)cs={margin:'170px 0px'}
$y(space_holder_div,cs);parent.appendChild(space_holder_div);}
remove_space_holder=function(){if(space_holder_div.parentNode)
space_holder_div.parentNode.removeChild(space_holder_div);};wn.urllib={get_arg:function(name){name=name.replace(/[\[]/,"\\\[").replace(/[\]]/,"\\\]");var regexS="[\\?&]"+name+"=([^&#]*)";var regex=new RegExp(regexS);var results=regex.exec(window.location.href);if(results==null)
return"";else
return decodeURIComponent(results[1]);},get_dict:function(){var d={}
var t=window.location.href.split('?')[1];if(!t)return d;if(t.indexOf('#')!=-1)t=t.split('#')[0];if(!t)return d;t=t.split('&');for(var i=0;i<t.length;i++){var a=t[i].split('=');d[decodeURIComponent(a[0])]=decodeURIComponent(a[1]);}
return d;},get_base_url:function(){var url=window.location.href.split('#')[0].split('?')[0].split('index.cgi')[0];if(url.substr(url.length-1,1)=='/')url=url.substr(0,url.length-1)
return url},get_file_url:function(file_id){var ac_id=locals['Control Panel']['Control Panel'].account_id;return repl('cgi-bin/getfile.cgi?name=%(fn)s&acx=%(ac)s',{fn:file_id,ac:ac_id})}}
get_url_arg=wn.urllib.get_arg;get_url_dict=wn.urllib.get_dict;var user_img={}
var user_img_queue={};var user_img_loading=[];set_user_img=function(img,username,get_latest,img_id){function set_it(i){if(user_img[username]=='no_img_m')
i.src='images/ui/no_img/no_img_m.gif';else if(user_img[username]=='no_img_f')
i.src='images/ui/no_img/no_img_f.gif';else{ac_id=locals['Control Panel']['Control Panel'].account_id;i.src=repl('cgi-bin/getfile.cgi?ac=%(ac)s&name=%(fn)s',{fn:user_img[username],ac:ac_id});}}
if(img_id){user_img[username]=img_id;set_it(img);return;}
if(user_img[username]&&!get_latest){set_it(img);}else{if(in_list(user_img_loading,username)){if(!user_img_queue[username])
user_img_queue[username]=[];user_img_queue[username].push(img);return;}
$c('webnotes.profile.get_user_img',{username:username},function(r,rt){delete user_img_loading[user_img_loading.indexOf(username)];user_img[username]=r.message;if(user_img_queue[username]){var q=user_img_queue[username];for(var i in q){set_it(q[i]);}}
set_it(img);},null,1);user_img_loading.push(username);}}
var outUrl="index.cgi";var NULL_CHAR='^\5*';function checkResponse(r,on_timeout,no_spinner,freeze_msg){try{if(r.readyState==4&&r.status==200)return true;else return false;}catch(e){msgprint("error:Request timed out, try again");if(on_timeout)
on_timeout();hide_loading();if(freeze_msg)
unfreeze();return false;}}
var pending_req=0;function newHttpReq(){if(!isIE)
var r=new XMLHttpRequest();else if(window.ActiveXObject)
var r=new ActiveXObject("Microsoft.XMLHTTP");return r;}
function $c(command,args,fn,on_timeout,no_spinner,freeze_msg){var req=newHttpReq();ret_fn=function(){if(checkResponse(req,on_timeout,no_spinner,freeze_msg)){if(!no_spinner)hide_loading();var rtxt=req.responseText;try{var r=JSON.parse(rtxt);}catch(e){alert('Handler Exception:'+rtxt);return;}
if(freeze_msg)unfreeze();if(!validate_session(r,rtxt))return;if(r.exc){errprint(r.exc);};if(r.server_messages){msgprint(r.server_messages);};if(r.docs){LocalDB.sync(r.docs);}
saveAllowed=true;if(fn)fn(r,rtxt);}}
req.onreadystatechange=ret_fn;req.open("POST",outUrl,true);req.setRequestHeader("ENCTYPE","multipart/form-data");req.setRequestHeader("Content-Type","application/x-www-form-urlencoded; charset=UTF-8");args['cmd']=command;req.send(makeArgString(args));if(!no_spinner)set_loading();if(freeze_msg)freeze(freeze_msg,1);}
function validate_session(r,rt){if(r.message=='Logged In'){start_sid=get_cookie('sid');return true;}
if(start_sid&&start_sid!=get_cookie('sid')&&user!='Guest'){page_body.set_session_changed();return;}
if(r.exc&&r.session_status=='Session Expired'){resume_session();return;}
if(r.exc&&r.session_status=='Logged Out'){msgprint('You have been logged out');setTimeout('redirect_to_login()',3000);return;}
if(r.exc&&r.exc_type&&r.exc_type=='PermissionError'){loadpage('_home');}
return true;}
function $c_obj(doclist,method,arg,call_back,no_spinner,freeze_msg){var args={'method':method,'arg':(typeof arg=='string'?arg:JSON.stringify(arg))}
if(typeof doclist=='string')args.doctype=doclist;else args.docs=compress_doclist(doclist)
$c('runserverobj',args,call_back,null,no_spinner,freeze_msg);}
function $c_page(module,page,method,arg,call_back,no_spinner,freeze_msg){if(arg&&!arg.substr)arg=JSON.stringify(arg);$c(module+'.page.'+page+'.'+page+'.'+method,{'arg':arg},call_back,null,no_spinner,freeze_msg);}
function $c_obj_csv(doclist,method,arg){var args={}
args.cmd='runserverobj';args.as_csv=1;args.method=method;args.arg=arg;if(doclist.substr)
args.doctype=doclist;else
args.docs=compress_doclist(doclist);open_url_post(outUrl,args);}
function $c_graph(img,control_dt,method,arg){img.src=outUrl+'?'+makeArgString({cmd:'get_graph',dt:control_dt,method:method,arg:arg});}
function my_eval(co){var w=window;if(!w.execScript){if(/Gecko/.test(navigator.userAgent)){eval(co,w);}else{eval.call(w,co);}}else{w.execScript(co);}}
function $c_js(fn,callback){var req=newHttpReq();ret_fn=function(){if(checkResponse(req,function(){},1,null)){if(req.responseText.substr(0,9)=='Not Found'){alert(req.responseText);return;}
hide_loading();my_eval(req.responseText);callback();}}
req.onreadystatechange=ret_fn;req.open("POST",'cgi-bin/getjsfile.cgi',true);req.setRequestHeader("ENCTYPE","multipart/form-data");req.setRequestHeader("Content-Type","application/x-www-form-urlencoded; charset=UTF-8");req.send(makeArgString({filename:fn}));set_loading();}
var load_queue={};var currently_loading={};var widgets={};var single_widgets={};function new_widget(widget,callback,single_type){var namespace='';var widget_name=widget;if(widget.search(/\./)!=-1){namespace=widget.split('.')[0];widget_name=widget.split('.')[1];}
var widget_loaded=function(){currently_loading[widget]=0;for(var i in load_queue[widget]){load_queue[widget][i](create_widget());}
load_queue[widget]=[];}
var create_widget=function(){if(single_type&&single_widgets[widget_name])
return null;if(namespace)
var w=new window[namespace][widget_name]();else
var w=new window[widget_name]();if(single_type)
single_widgets[widget_name]=w;return w;}
if(namespace?window[namespace][widget_name]:window[widget_name]){callback(create_widget());}else{if(!load_queue[widget])load_queue[widget]=[];load_queue[widget].push(callback);if(!currently_loading[widget]){$c_js(widget_files[widget],widget_loaded);}
currently_loading[widget]=1;}}
function makeArgString(dict){var varList=[];for(key in dict){varList[varList.length]=key+'='+encodeURIComponent(dict[key]);}
return varList.join('&');}
function open_url_post(URL,PARAMS,new_window){var temp=document.createElement("form");temp.action=URL;temp.method="POST";temp.style.display="none";if(new_window){}
for(var x in PARAMS){var opt=document.createElement("textarea");opt.name=x;opt.value=PARAMS[x];temp.appendChild(opt);}
document.body.appendChild(temp);temp.submit();return temp;}
var resume_dialog=null;function resume_session(){if(!resume_dialog){var d=new Dialog(400,200,'Session Expired');d.make_body([['Password','password','Re-enter your password to resume the session'],['Button','Go']]);d.widgets['Go'].onclick=function(){resume_dialog.widgets['Go'].set_working();var callback=function(r,rt){resume_dialog.widgets['Go'].done_working();if(r.message=='Logged In'){resume_dialog.allow_close=1;resume_dialog.hide();setTimeout('resume_dialog.allow_close=0',100);}else{msgprint('Wrong Password, try again');resume_dialog.wrong_count++;if(resume_dialog.wrong_count>2)logout();}}
$c('resume_session',{pwd:resume_dialog.widgets['password'].value},callback)}
d.onhide=function(){if(!resume_dialog.allow_close)logout();}
resume_dialog=d;}
resume_dialog.wrong_count=0;resume_dialog.show();}
var msg_dialog;function msgprint(msg,issmall,callback){if(!msg)return;if(typeof(msg)!='string')
msg=JSON.stringify(msg);if(issmall){show_alert(msg);return;}
if(msg.substr(0,8)=='__small:'){show_alert(msg.substr(8));return;}
if(!msg_dialog){msg_dialog=new Dialog(500,200,"Message");msg_dialog.make_body([['HTML','Msg']])
msg_dialog.onhide=function(){msg_dialog.msg_area.innerHTML='';$dh(msg_dialog.msg_icon);if(msg_dialog.custom_onhide)msg_dialog.custom_onhide();}
$y(msg_dialog.rows['Msg'],{fontSize:'14px',lineHeight:'1.5em',padding:'16px'})
var t=make_table(msg_dialog.rows['Msg'],1,2,'100%',['20px','250px'],{padding:'2px',verticalAlign:'Top'});msg_dialog.msg_area=$td(t,0,1);msg_dialog.msg_icon=$a($td(t,0,0),'img');}
if(!msg_dialog.display)msg_dialog.show();var has_msg=msg_dialog.msg_area.innerHTML?1:0;var m=$a(msg_dialog.msg_area,'div','');if(has_msg)$y(m,{marginTop:'4px'});$dh(msg_dialog.msg_icon);if(msg.substr(0,6).toLowerCase()=='error:'){msg_dialog.msg_icon.src='images/icons/error.gif';$di(msg_dialog.msg_icon);msg=msg.substr(6);}else if(msg.substr(0,8).toLowerCase()=='message:'){msg_dialog.msg_icon.src='images/icons/application.gif';$di(msg_dialog.msg_icon);msg=msg.substr(8);}else if(msg.substr(0,3).toLowerCase()=='ok:'){msg_dialog.msg_icon.src='images/icons/accept.gif';$di(msg_dialog.msg_icon);msg=msg.substr(3);}
m.innerHTML=replace_newlines(msg);if(m.offsetHeight>200){$y(m,{height:'200px',width:'400px',overflow:'auto'})}
msg_dialog.custom_onhide=callback;}
var growl_area;function show_alert(txt){if(!growl_area){growl_area=$a(popup_cont,'div','',{position:'fixed',bottom:'8px',right:'8px',width:'320px',zIndex:10});}
var wrapper=$a(growl_area,'div','',{position:'relative'});var body=$a(wrapper,'div','notice');var c=$a(body,'div','wn-icon ic-round_delete',{cssFloat:'right'});$(c).click(function(){$dh(this.wrapper)});c.wrapper=wrapper;var t=$a(body,'div','',{color:'#FFF'});$(t).html(txt);$(wrapper).hide().fadeIn(1000);}
if(!this.JSON){this.JSON={};}
(function(){function f(n){return n<10?'0'+n:n;}
if(typeof Date.prototype.toJSON!=='function'){Date.prototype.toJSON=function(key){return isFinite(this.valueOf())?this.getUTCFullYear()+'-'+
f(this.getUTCMonth()+1)+'-'+
f(this.getUTCDate())+'T'+
f(this.getUTCHours())+':'+
f(this.getUTCMinutes())+':'+
f(this.getUTCSeconds())+'Z':null;};String.prototype.toJSON=Number.prototype.toJSON=Boolean.prototype.toJSON=function(key){return this.valueOf();};}
var cx=/[\u0000\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,escapable=/[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,gap,indent,meta={'\b':'\\b','\t':'\\t','\n':'\\n','\f':'\\f','\r':'\\r','"':'\\"','\\':'\\\\'},rep;function quote(string){escapable.lastIndex=0;return escapable.test(string)?'"'+string.replace(escapable,function(a){var c=meta[a];return typeof c==='string'?c:'\\u'+('0000'+a.charCodeAt(0).toString(16)).slice(-4);})+'"':'"'+string+'"';}
function str(key,holder){var i,k,v,length,mind=gap,partial,value=holder[key];if(value&&typeof value==='object'&&typeof value.toJSON==='function'){value=value.toJSON(key);}
if(typeof rep==='function'){value=rep.call(holder,key,value);}
switch(typeof value){case'string':return quote(value);case'number':return isFinite(value)?String(value):'null';case'boolean':case'null':return String(value);case'object':if(!value){return'null';}
gap+=indent;partial=[];if(Object.prototype.toString.apply(value)==='[object Array]'){length=value.length;for(i=0;i<length;i+=1){partial[i]=str(i,value)||'null';}
v=partial.length===0?'[]':gap?'[\n'+gap+
partial.join(',\n'+gap)+'\n'+
mind+']':'['+partial.join(',')+']';gap=mind;return v;}
if(rep&&typeof rep==='object'){length=rep.length;for(i=0;i<length;i+=1){k=rep[i];if(typeof k==='string'){v=str(k,value);if(v){partial.push(quote(k)+(gap?': ':':')+v);}}}}else{for(k in value){if(Object.hasOwnProperty.call(value,k)){v=str(k,value);if(v){partial.push(quote(k)+(gap?': ':':')+v);}}}}
v=partial.length===0?'{}':gap?'{\n'+gap+partial.join(',\n'+gap)+'\n'+
mind+'}':'{'+partial.join(',')+'}';gap=mind;return v;}}
if(typeof JSON.stringify!=='function'){JSON.stringify=function(value,replacer,space){var i;gap='';indent='';if(typeof space==='number'){for(i=0;i<space;i+=1){indent+=' ';}}else if(typeof space==='string'){indent=space;}
rep=replacer;if(replacer&&typeof replacer!=='function'&&(typeof replacer!=='object'||typeof replacer.length!=='number')){throw new Error('JSON.stringify');}
return str('',{'':value});};}
if(typeof JSON.parse!=='function'){JSON.parse=function(text,reviver){var j;function walk(holder,key){var k,v,value=holder[key];if(value&&typeof value==='object'){for(k in value){if(Object.hasOwnProperty.call(value,k)){v=walk(value,k);if(v!==undefined){value[k]=v;}else{delete value[k];}}}}
return reviver.call(holder,key,value);}
cx.lastIndex=0;if(cx.test(text)){text=text.replace(cx,function(a){return'\\u'+
('0000'+a.charCodeAt(0).toString(16)).slice(-4);});}
if(/^[\],:{}\s]*$/.test(text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g,'@').replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,']').replace(/(?:^|:|,)(?:\s*\[)+/g,''))){j=eval('('+text+')');return typeof reviver==='function'?walk({'':j},''):j;}
throw new SyntaxError('JSON.parse');};}}());(function(jQuery){jQuery.hotkeys={version:"0.8",specialKeys:{8:"backspace",9:"tab",13:"return",16:"shift",17:"ctrl",18:"alt",19:"pause",20:"capslock",27:"esc",32:"space",33:"pageup",34:"pagedown",35:"end",36:"home",37:"left",38:"up",39:"right",40:"down",45:"insert",46:"del",96:"0",97:"1",98:"2",99:"3",100:"4",101:"5",102:"6",103:"7",104:"8",105:"9",106:"*",107:"+",109:"-",110:".",111:"/",112:"f1",113:"f2",114:"f3",115:"f4",116:"f5",117:"f6",118:"f7",119:"f8",120:"f9",121:"f10",122:"f11",123:"f12",144:"numlock",145:"scroll",191:"/",224:"meta"},shiftNums:{"`":"~","1":"!","2":"@","3":"#","4":"$","5":"%","6":"^","7":"&","8":"*","9":"(","0":")","-":"_","=":"+",";":": ","'":"\"",",":"<",".":">","/":"?","\\":"|"}};function keyHandler(handleObj){if(typeof handleObj.data!=="string"){return;}
var origHandler=handleObj.handler,keys=handleObj.data.toLowerCase().split(" ");handleObj.handler=function(event){if(this!==event.target&&(/textarea|select/i.test(event.target.nodeName)||event.target.type==="text")){return;}
var special=event.type!=="keypress"&&jQuery.hotkeys.specialKeys[event.which],character=String.fromCharCode(event.which).toLowerCase(),key,modif="",possible={};if(event.altKey&&special!=="alt"){modif+="alt+";}
if(event.ctrlKey&&special!=="ctrl"){modif+="ctrl+";}
if(event.metaKey&&!event.ctrlKey&&special!=="meta"){modif+="meta+";}
if(event.shiftKey&&special!=="shift"){modif+="shift+";}
if(special){possible[modif+special]=true;}else{possible[modif+character]=true;possible[modif+jQuery.hotkeys.shiftNums[character]]=true;if(modif==="shift+"){possible[jQuery.hotkeys.shiftNums[character]]=true;}}
for(var i=0,l=keys.length;i<l;i++){if(possible[keys[i]]){return origHandler.apply(this,arguments);}}};}
jQuery.each(["keydown","keyup","keypress"],function(){jQuery.event.special[this]={add:keyHandler};});})(jQuery);;(function(window,undefined){var document=window["document"];var $=window["jQuery"];$.fn["printElement"]=function(options){var mainOptions=$.extend({},$.fn["printElement"]["defaults"],options);if(mainOptions["printMode"]=='iframe'){if($.browser.opera||(/chrome/.test(navigator.userAgent.toLowerCase())))
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
html.push('<base href="'+_getBaseHref()+'" />');html.push('</head><body style="'+opts["printBodyOptions"]["styleToAdd"]+'" class="'+opts["printBodyOptions"]["classNameToAdd"]+'">');html.push('<div class="'+$element.attr('class')+'">'+elementHtml+'</div>');html.push('<script type="text/javascript">function printPage(){focus();print();'+((!$.browser.opera&&!opts["leaveOpen"]&&opts["printMode"].toLowerCase()=='popup')?'close();':'')+'}</script>');html.push('</body></html>');return html.join('');};})(window);wn.widgets.FieldGroup=function(){this.make_fields=function(body,fl){$y(this.body,{padding:'11px'});this.fields_dict={};for(var i=0;i<fl.length;i++){var df=fl[i];var div=$a(body,'div','',{margin:'6px 0px'})
f=make_field(df,null,div,null);f.not_in_form=1;this.fields_dict[df.fieldname]=f
f.refresh();}}
this.get_values=function(){var ret={};var errors=[];for(var key in this.fields_dict){var f=this.fields_dict[key];var v=f.get_value?f.get_value():null;if(f.df.reqd&&!v)
errors.push(f.df.label+' is mandatory');if(v)ret[f.df.fieldname]=v;}
if(errors.length){msgprint('<b>Please check the following Errors</b>\n'+errors.join('\n'));return null;}
return ret;}
this.set_value=function(key,val){var f=this.fields_dict[key];if(f){f.set_input(val);f.refresh_mandatory();}}
this.set_values=function(dict){for(var key in dict){if(this.fields_dict[key]){this.set_value(key,dict[key]);}}}}
wn.widgets.Dialog=function(opts){this.opts=opts;this.display=false;this.make=function(opts){if(opts)this.opts=opts;this.wrapper=$a(popup_cont,'div','dialog_wrapper');if(this.opts.width)
this.wrapper.style.width=this.opts.width+'px';this.make_head();this.body=$a(this.wrapper,'div','dialog_body');if(this.opts.fields)
this.make_fields(this.body,this.opts.fields);}
this.make_head=function(){var me=this;this.head=$a(this.wrapper,'div','dialog_head');var t=make_table(this.head,1,2,'100%',['100%','16px'],{padding:'2px'});$y($td(t,0,0),{paddingLeft:'16px',fontWeight:'bold',fontSize:'14px',textAlign:'center'});$y($td(t,0,1),{textAlign:'right'});var img=$a($td(t,0,01),'img','',{cursor:'pointer'});img.src='images/icons/close.gif';this.title_text=$td(t,0,0);this.set_title(this.opts.title);img.onclick=function(){if(me.oncancel)me.oncancel();me.hide();}
this.cancel_img=img;}
this.set_title=function(t){this.title_text.innerHTML=t?t:'';}
this.set_postion=function(){var d=get_screen_dims();this.wrapper.style.left=((d.w-cint(this.wrapper.style.width))/2)+'px';this.wrapper.style.top=(get_scroll_top()+60)+'px';top_index++;$y(this.wrapper,{zIndex:top_index});}
this.show=function(){if(this.display)return;this.set_postion()
$ds(this.wrapper);freeze();this.display=true;cur_dialog=this;if(this.onshow)this.onshow();}
this.hide=function(){if(this.onhide)this.onhide();unfreeze();$dh(this.wrapper);if(cur_autosug)cur_autosug.clearSuggestions();this.display=false;cur_dialog=null;}
this.no_cancel=function(){$dh(this.cancel_img);}
if(opts)this.make();}
wn.widgets.Dialog.prototype=new wn.widgets.FieldGroup();keypress_observers.push(new function(){this.notify_keypress=function(e,kc){if(cur_dialog&&kc==27&&!cur_dialog.no_cancel_flag)
cur_dialog.hide();}});var cur_dialog;var top_index=91;function Dialog(w,h,title,content){this.make({width:w,title:title});if(content)this.make_body(content);this.onshow='';this.oncancel='';this.no_cancel_flag=0;this.display=false;var me=this;}
Dialog.prototype=new wn.widgets.Dialog()
Dialog.prototype.make_body=function(content){this.rows={};this.widgets={};for(var i in content)this.make_row(content[i]);}
Dialog.prototype.clear_inputs=function(d){for(var wid in this.widgets){var w=this.widgets[wid];var tn=w.tagName?w.tagName.toLowerCase():'';if(tn=='input'||tn=='textarea'){w.value='';}else if(tn=='select'){sel_val(w.options[0].value);}else if(w.txt){w.txt.value='';}else if(w.input){w.input.value='';}}}
Dialog.prototype.make_row=function(d){var me=this;this.rows[d[1]]=$a(this.body,'div','dialog_row');var row=this.rows[d[1]];if(d[0]!='HTML'){var t=make_table(row,1,2,'100%',['30%','70%']);row.tab=t;var c1=$td(t,0,0);var c2=$td(t,0,1);if(d[0]!='Check'&&d[0]!='Button')
$t(c1,d[1]);}
if(d[0]=='HTML'){if(d[2])row.innerHTML=d[2];this.widgets[d[1]]=row;}
else if(d[0]=='Check'){var i=$a_input(c2,'checkbox','',{width:'20px'});c1.innerHTML=d[1];this.widgets[d[1]]=i;}
else if(d[0]=='Data'){c1.innerHTML=d[1];c2.style.overflow='auto';this.widgets[d[1]]=$a_input(c2,'text');if(d[2])$a(c2,'div','comment').innerHTML=d[2];}
else if(d[0]=='Link'){c1.innerHTML=d[1];var f=make_field({fieldtype:'Link','label':d[1],'options':d[2]},'',c2,this,0,1);f.not_in_form=1;f.dialog=this;f.refresh();this.widgets[d[1]]=f.input;}
else if(d[0]=='Date'){c1.innerHTML=d[1];var f=make_field({fieldtype:'Date','label':d[1],'options':d[2]},'',c2,this,0,1);f.not_in_form=1;f.refresh();f.dialog=this;this.widgets[d[1]]=f.input;}
else if(d[0]=='Password'){c1.innerHTML=d[1];c2.style.overflow='auto';this.widgets[d[1]]=$a_input(c2,'password');if(d[3])$a(c2,'div','comment').innerHTML=d[3];}
else if(d[0]=='Select'){c1.innerHTML=d[1];this.widgets[d[1]]=$a(c2,'select','',{width:'160px'})
if(d[2])$a(c2,'div','comment').innerHTML=d[2];if(d[3])add_sel_options(this.widgets[d[1]],d[3],d[3][0]);}
else if(d[0]=='Text'){c1.innerHTML=d[1];c2.style.overflow='auto';this.widgets[d[1]]=$a(c2,'textarea');if(d[2])$a(c2,'div','comment').innerHTML=d[2];}
else if(d[0]=='Button'){c2.style.height='32px';c2.style.textAlign='right';var b=$btn(c2,d[1],function(btn){if(btn._onclick)btn._onclick(me)},null,null,1);b.dialog=me;if(d[2]){b._onclick=d[2];}
this.widgets[d[1]]=b;}}
list_opts={cell_style:{padding:'3px 2px'},alt_cell_style:{},head_style:{height:'20px',overflow:'hidden',verticalAlign:'middle',fontWeight:'bold',padding:'1px',fontSize:'13px'},head_main_style:{padding:'0px'},hide_export:1,hide_print:1,hide_refresh:0,hide_rec_label:0,show_calc:1,show_empty_tab:0,no_border:1,append_records:1,table_width:null};function Listing(head_text,no_index,no_loading){this.start=0;this.page_len=20;this.filters_per_line=7;this.cell_idx=0;this.head_text=head_text?head_text:'Result';this.keyword='records';this.no_index=no_index;this.underline=1;this.no_rec_message='No Result';this.show_cell=null;this.show_result=null;this.colnames=null;this.colwidths=null;this.coltypes=null;this.coloptions=null;this.filters={};this.sort_list={};this.sort_order_dict={};this.sort_heads={};this.is_std_query=false;this.server_call=null;this.no_loading=no_loading;this.opts=copy_dict(list_opts);}
Listing.prototype.make=function(parent){var me=this;this.wrapper=parent;this.filter_wrapper=$a(parent,'div','srs_filter_wrapper');this.filter_area=$a(this.filter_wrapper,'div','srs_filter_area');$dh(this.filter_wrapper);this.btn_area=$a(parent,'div','',{margin:'8px 0px'});this.body_area=$a(parent,'div','srs_body_area');if(!this.opts.hide_rec_label)
this.rec_label=$a(this.body_area,'div','',{margin:'4px 0px',color:'#888'});this.results=$a($a(this.body_area,'div','srs_results_area'),'div');this.fetching_area=$a(this.body_area,'div','',{height:'120px',background:'url("images/ui/square_loading.gif") center no-repeat',display:'none'});this.show_no_records=$a(this.body_area,'div','',{margin:'200px 0px',textAlign:'center',fontSize:'14px',color:'#888',display:'none'});this.show_no_records.innerHTML='No Result';if(this.opts.show_empty_tab)
this.make_result_tab();this.bottom_div=$a(this.body_area,'div','',{paddingTop:'8px'});this.make_toolbar();}
Listing.prototype.make_toolbar=function(){var me=this;this.buttons={};var make_btn=function(label,icon,onclick,bold){var btn=$btn(me.btn_area,label,onclick,{marginRight:'4px'});if(bold)$y(btn,{fontWeight:'bold'});me.buttons[label]=btn;}
if(!this.opts.hide_refresh){make_btn('Refresh','ui-icon-refresh',function(btn){me.start=0;me.run();},1);}
if(this.opts.show_new){make_btn('New ','ui-icon-document',function(){new_doc(me.dt);},1);}
if(this.opts.show_report){make_btn('Report Builder','ui-icon-clipboard',function(){loadreport(me.dt,null,null,null,1);},0);}
if(!this.opts.hide_export){make_btn('Export','ui-icon-circle-arrow-e',function(){me.do_export();});}
if(!this.opts.hide_print){make_btn('Print','ui-icon-print',function(){me.do_print();});}
if(this.opts.show_calc){make_btn('Calc','ui-icon-calculator',function(){me.do_calc();});$dh(me.buttons['Calc'])}
this.loading_img=$a(this.btn_area,'img','',{display:'none',marginBottom:'-2px'});this.loading_img.src='images/ui/button-load.gif';if(!keys(this.buttons).length)
$dh(this.btn_area);}
Listing.prototype.do_print=function(){this.build_query();if(!this.query){alert('No Query!');return;}
args={query:this.query,title:this.head_text,colnames:this.colnames,colwidths:this.colwidths,coltypes:this.coltypes,has_index:(this.no_index?0:1),has_headings:1,check_limit:1,is_simple:1}
new_widget('_p.PrintQuery',function(w){if(!_p.print_query)
_p.print_query=w;_p.print_query.show_dialog(args);},1);}
Listing.prototype.do_calc=function(){show_calc(this.result_tab,this.colnames,this.coltypes,0)}
Listing.prototype.add_filter=function(label,ftype,options,tname,fname,cond){if(!this.filter_area){alert('[Listing] make() must be called before add_filter');}
var me=this;if(!this.filter_set){var h=$a(this.filter_area,'div','',{fontSize:'14px',fontWeight:'bold',marginBottom:'4px'});h.innerHTML='Filter your search';this.filter_area.div=$a(this.filter_area,'div');this.perm=[[1,1],]
this.filters={};}
$ds(this.filter_wrapper);if((!this.inp_tab)||(this.cell_idx==this.filters_per_line)){this.inp_tab=$a(this.filter_area.div,'table','',{width:'100%',tableLayout:'fixed'});this.inp_tab.insertRow(0);for(var i=0;i<this.filters_per_line;i++){this.inp_tab.rows[0].insertCell(i);}
this.cell_idx=0;}
var c=this.inp_tab.rows[0].cells[this.cell_idx];this.cell_idx++;$y(c,{width:cint(100/this.filters_per_line)+'%',textAlign:'left',verticalAlign:'top'});var d1=$a(c,'div','',{fontSize:'11px',marginBottom:'2px'});d1.innerHTML=label;if(ftype=='Link')d1.innerHTML+=' <img src="images/icons/link.png" style="margin-bottom:-5px" title="Link">';var d2=$a(c,'div');if(in_list(['Text','Small Text','Code','Text Editor','Read Only'],ftype))
ftype='Data';if(ftype=='Select'&&!in_list(options.split('\n'),''))options='\n'+options
var inp=make_field({fieldtype:ftype,'label':label,'options':options,no_buttons:1},'',d2,this,0,1);inp.not_in_form=1;inp.report=this;inp.df.single_select=1;inp.parent_cell=c;inp.parent_tab=this.input_tab;$y(inp.wrapper,{width:'95%'});inp.refresh();inp.tn=tname;inp.fn=fname;inp.condition=cond;var me=this;inp.onchange=function(){me.start=0;}
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
wn.widgets.Listing=function(opts){this.opts=opts;this.page_length=20;this.btns={};this.start=0;var me=this;this.make=function(opts){this.wrapper=$a(this.opts.parent,'div');this.filters_area=$a(this.wrapper,'div','listing-filters');this.toolbar_area=$a(this.wrapper,'div','listing-toolbar');this.results_area=$a(this.wrapper,'div','listing-results');this.more_button_area=$a(this.wrapper,'div','listing-more');this.no_results_area=$a(this.wrapper,'div','help_box',{display:'none'},(this.opts.no_result_message?this.opts.no_result_message:'No results'));if(opts)this.opts=opts;this.page_length=this.opts.page_length?this.opts.page_length:this.page_length;this.make_toolbar();this.make_filters();this.make_more_button();}
this.make_filters=function(){if(this.opts.filters){$ds(this.filters_area);this.filters=new wn.widgets.FieldGroup(this.filters_area,this.opts.fields);}}
this.make_toolbar=function(){if(!this.opts.hide_refresh){this.ref_img=$a(this.toolbar_area,'span','link_type',{color:'#888'},'[refresh]');this.ref_img.onclick=function(){me.run();}
this.loading_img=$a(this.toolbar_area,'img','images/ui/button-load.gif',{display:'none',marginLeft:'3px',marginBottom:'-2px'});}
if(this.opts.new_doctype){this.new_btn=$btn(this.toolbar_area,'New '+get_doctype_label(this.opts.new_doctype),function(){newdoc(me.opts.new_doctype,me.opts.new_doc_onload,me.opts.new_doc_indialog,me.opts.new_doc_onsave);},{marginLeft:'7px'});}}
this.make_more_button=function(){this.more_btn=$btn(this.more_button_area,'Show more results...',function(){me.more_btn.set_working();me.run(function(){me.more_btn.done_working();},1);},{fontSize:'14px'},0,1);$y(this.more_btn.loading_img,{marginBottom:'0px'});}
this.clear=function(){this.results_area.innerHTML='';this.table=null;$ds(this.results_area);$dh(this.no_results_area);}
this.make_results=function(r,rt){if(this.start==0)this.clear();$dh(this.more_button_area);if(this.loading_img)$dh(this.loading_img)
if(r.values&&r.values.length){this.values=r.values;var m=Math.min(r.values.length,this.page_length);for(var i=0;i<m;i++){var row=this.add_row();this.opts.render_row(row,r.values[i],this,i);}
this.start+=m;if(r.values.length>this.page_length)$ds(this.more_button_area);}else{if(this.start==0){$dh(this.results_area);$ds(this.no_results_area);}}
if(this.onrun)this.onrun();if(this.opts.onrun)this.opts.onrun();}
this.add_row=function(){return $a(this.results_area,'div','',(opts.cell_style?opts.cell_style:{padding:'3px'}));}
this.run=function(callback,append){if(callback)
this.onrun=callback;if(!append)
this.start=0;this.query=this.opts.get_query();this.add_limits();args={query_max:this.query_max?this.query_max:''}
args.simple_query=this.query;if(this.opts.as_dict)args.as_dict=1;if(this.opts.formatted)args.formatted=1;if(this.loading_img)$di(this.loading_img);$c('webnotes.widgets.query_builder.runquery',args,function(r,rt){me.make_results(r,rt)},null,this.opts.no_loading);}
this.add_limits=function(){this.query+=' LIMIT '+this.start+','+(this.page_length+1);}
if(opts)this.make();}
function Tree(parent,width,do_animate){this.width=width;this.nodes={};this.allnodes={};this.cur_node;this.is_root=1;this.do_animate=do_animate;var me=this;this.exp_img='images/icons/plus.gif';this.col_img='images/icons/minus.gif';this.body=$a(parent,'div');if(width)$w(this.body,width);this.addNode=function(parent,id,imagesrc,onclick,onexpand,opts,label){var t=new TreeNode(me,parent,id,imagesrc,onclick,onexpand,opts,label);if(!parent){me.nodes[id]=t;}else{parent.nodes[id]=t;}
me.allnodes[id]=t;if(onexpand)
t.create_expimage();t.expanded_once=0;return t;}
var me=this;this.collapseall=function(){for(n in me.allnodes){me.allnodes[n].collapse();}}}
function TreeNode(tree,parent,id,imagesrc,onclick,onexpand,opts,label){var me=this;if(!parent)parent=tree;this.parent=parent;this.nodes={};this.onclick=onclick;this.onexpand=onexpand;this.text=label?label:id;this.tree=tree;if(opts)
this.opts=opts;else
this.opts={show_exp_img:1,show_icon:1,label_style:{padding:'2px',cursor:'pointer',fontSize:'11px'},onselect_style:{fontWeight:'bold'},ondeselect_style:{fontWeight:'normal'}}
var tc=1;if(this.opts.show_exp_img)tc+=1;if(!this.parent.tab){this.parent.tab=make_table(this.parent.body,2,tc,'100%');$y(this.parent.tab,{tableLayout:'fixed',borderCollapse:'collapse'});}else{this.parent.tab.append_row();this.parent.tab.append_row();}
var mytab=this.parent.tab;if(this.opts.show_exp_img){this.exp_cell=$td(mytab,mytab.rows.length-2,0);$y(this.exp_cell,{cursor:'pointer',textAlign:'center',verticalAlign:'middle',width:'20px'});this.exp_cell.innerHTML='&nbsp;';}else{}
this.create_expimage=function(){if(!me.opts.show_exp_img)return;if(!me.expimage){me.exp_cell.innerHTML='';me.expimage=$a(me.exp_cell,'img');me.expimage.src=me.exp_img?me.exp_img:me.tree.exp_img;me.expimage.onclick=me.toggle;}}
this.label=$a($td(mytab,mytab.rows.length-2,tc-1),'div');$y(this.label,this.opts.label_style);if(this.opts.show_icon){var t2=make_table($a(this.label,'div'),1,2,'100%',['20px',null]);$y(t2,{borderCollapse:'collapse'});this.img_cell=$td(t2,0,0);$y(this.img_cell,{cursor:'pointer',verticalAlign:'middle',width:'20px'});if(!imagesrc)imagesrc="images/icons/folder.gif";this.usrimg=$a(this.img_cell,'img');this.usrimg.src=imagesrc;this.label=$td(t2,0,1);$y(this.label,{verticalAlign:'middle'});}
this.loading_div=$a($td(mytab,mytab.rows.length-1,this.opts.show_exp_img?1:0),"div","comment",{fontSize:'11px'});$dh(this.loading_div);this.loading_div.innerHTML='Loading...';this.body=$a($td(mytab,mytab.rows.length-1,this.opts.show_exp_img?1:0),"div",'',{overflow:'hidden',display:'none'});this.select=function(){me.show_selected();if(me.onclick)me.onclick(me);}
this.show_selected=function(){if(me.tree.cur_node)me.tree.cur_node.deselect();if(me.opts.onselect_style)$y(me.label,me.opts.onselect_style)
me.tree.cur_node=me;}
this.deselect=function(){if(me.opts.ondeselect_style)$y(me.label,me.opts.ondeselect_style)
me.tree.cur_node=null}
this.expanded=0;this.toggle=function(){if(me.expanded)
me.collapse();else
me.expand();}
this.collapse=function(){me.expanded=0;$(me.body).slideUp();me.expimage.src=me.exp_img?me.exp_img:me.tree.exp_img;}
this.expand=function(){if(me.onexpand&&!me.expanded_once){me.onexpand(me);if(!me.tree.do_animate)me.show_expanded();}else{me.show_expanded();}
me.expanded=1;me.expanded_once=1;me.expimage.src=me.col_img?me.col_img:me.tree.col_img;}
this.show_expanded=function(){if(me.tree.do_animate&&(!keys(me.nodes).length))return;$(me.body).slideDown();}
this.setlabel=function(l){me.label.value=l;me.label.innerHTML=l;}
this.setlabel(this.text);this.setcolor=function(c){this.backColor=c;if(cur_node!=this)
$bg(this.body,this.backColor);}
this.label.onclick=function(e){me.select();}
this.label.ondblclick=function(e){me.select();if(me.ondblclick)me.ondblclick(me);}
this.clear_child_nodes=function(){if(this.tab){this.tab.parentNode.removeChild(this.tab);delete this.tab;}
this.expanded_once=0;}}
function MenuToolbar(parent){this.ul=$a(parent,'ul','menu_toolbar');this.cur_top_menu=null;this.max_rows=10;this.dropdown_width='280px';this.top_menus={};this.top_menu_style='top_menu';this.top_menu_mo_style='top_menu_mo';this.top_menu_icon_style='top_menu_icon';}
MenuToolbar.prototype.add_top_menu=function(label,onclick,add_icon){var li=$a(this.ul,'li');li.item=new MenuToolbarItem(this,li,label,onclick,add_icon);this.top_menus[label]=li.item.wrapper;return li.item.wrapper;}
function MenuToolbarItem(tbar,parent,label,onclick,add_icon){var me=this;this.wrapper=$a(parent,'div',tbar.top_menu_style);if(add_icon){var t=make_table(this.wrapper,1,2,null,['22px',null],{verticalAlign:'middle'});$y(t,{borderCollapse:'collapse'});var icon=$a($td(t,0,0),'div','wntoolbar-icon '+add_icon);$td(t,0,1).innerHTML=label;}else{this.wrapper.innerHTML=label;}
this.wrapper.onclick=function(){onclick();};this.def_class=tbar.top_menu_style;this.wrapper.onmouseover=function(){this.set_selected();if(this.my_mouseover)this.my_mouseover(this);}
this.wrapper.onmouseout=function(){if(this.my_mouseout)
this.my_mouseout(this);this.set_unselected();}
this.wrapper.set_unselected=function(){if(me.wrapper.dropdown&&me.wrapper.dropdown.is_active){return;}
me.wrapper.className=me.def_class;}
this.wrapper.set_selected=function(){if(me.cur_top_menu)
me.cur_top_menu.set_unselected();me.wrapper.className=me.def_class+' '+tbar.top_menu_mo_style;me.cur_top_menu=this;}}
var closetimer;function mclose(opt){for(var i=0;i<all_dropdowns.length;i++){if(all_dropdowns[i].is_active)
if(opt&&opt==all_dropdowns[i]){}
else all_dropdowns[i].hide();}}
function mclosetime(){closetimer=window.setTimeout(mclose,700);}
function mcancelclosetime(){if(closetimer){window.clearTimeout(closetimer);closetimer=null;}}
MenuToolbar.prototype.make_dropdown=function(tm){var me=this;tm.dropdown=new DropdownMenu(tm,this.dropdown_width);tm.my_mouseover=function(){this.dropdown.show();}
tm.my_mouseout=function(){this.dropdown.clear();}}
MenuToolbar.prototype.add_item=function(top_menu_label,label,onclick,on_top){var me=this;var tm=this.top_menus[top_menu_label];if(!tm.dropdown)
this.make_dropdown(tm,this.dropdown_width);return tm.dropdown.add_item(label,onclick,on_top);}
var all_dropdowns=[];var cur_dropdown;function DropdownMenu(parent,width){this.body=$a(parent,'div','menu_toolbar_dropdown',{width:(width?width:'140px'),display:'none'});this.parent=parent;this.items={};this.item_style='dd_item';this.item_mo_style='dd_item_mo';this.list=[];this.max_height=400;this.keypressdelta=500;var me=this;this.body.onmouseout=function(){me.clear();}
this.body.onmouseover=function(){mcancelclosetime();}
this.clear_user_inp=function(){me.user_inp='';}
this.show=function(){mclose(me);mcancelclosetime();hide_selects();me.is_active=1;$ds(me.body);if(cint(me.body.clientHeight)>=me.max_height){$y(me.body,{height:me.max_height+'px'});me.scrollbars=1;}else{$y(me.body,{height:null});me.scrollbars=0;}}
this.hide=function(){$dh(me.body);if(!frozen)show_selects();me.is_active=0;if(me.parent&&me.parent.set_unselected){me.parent.set_unselected();}}
this.clear=function(){mcancelclosetime();mclosetime();}
all_dropdowns.push(me);}
DropdownMenu.prototype.add_item=function(label,onclick,on_top){var me=this;if(on_top){var mi=document.createElement('div');me.body.insertBefore(mi,me.body.firstChild);mi.className=this.item_style;}else{var mi=$a(this.body,'div',this.item_style);}
mi.innerHTML=label;mi.label=label;mi.my_onclick=onclick;mi.onclick=function(){mclose();this.my_onclick();};mi.highlight=function(){if(me.cur_mi)me.cur_mi.clear();this.className=me.item_style+' '+me.item_mo_style;me.cur_mi=this;}
mi.clear=function(){this.className=me.item_style;}
mi.onmouseover=mi.highlight;mi.onmouseout=mi.clear;mi.bring_to_top=function(){me.body.insertBefore(this,me.body.firstChild);}
return mi;}
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
function TabbedPage(parent,only_labels){this.tabs={};this.items=this.tabs
this.cur_tab=null;this.label_wrapper=$a(parent,'div','box_label_wrapper',{marginTop:'16px'});this.label_body=$a(this.label_wrapper,'div','box_label_body');this.label_area=$a(this.label_body,'ul','box_tabs');if(!only_labels)this.body_area=$a(parent,'div','',{backgroundColor:'#FFF'});else this.body_area=null;this.add_item=function(label,onclick,no_body,with_heading){this.add_tab(label,onclick,no_body,with_heading);return this.items[label];}}
TabbedPage.prototype.add_tab=function(n,onshow,no_body,with_heading){var tab=$a(this.label_area,'li');tab.label=$a(tab,'a');tab.label.innerHTML=n;if(this.body_area&&!no_body){tab.tab_body=$a(this.body_area,'div');$dh(tab.tab_body);tab.body=tab.tab_body;}else{tab.tab_body=null;}
tab.onshow=onshow;var me=this;tab.collapse=function(){if(this.tab_body)$dh(this.tab_body);this.className='';hide_autosuggest();}
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
var def_ph_style={wrapper:{marginBottom:'16px',backgroundColor:'#EEE'},main_heading:{},sub_heading:{marginBottom:'8px',color:'#555',display:'none'},separator:{borderTop:'3px solid #444'},toolbar_area:{padding:'3px 0px',display:'none',borderBottom:'1px solid #AAA'}}
function PageHeader(parent,main_text,sub_text){this.wrapper=$a(parent,'div','page_header');this.t1=make_table($a(this.wrapper,'div','',def_ph_style.wrapper.backgroundColor),1,2,'100%',[null,'100px'],{padding:'2px'});$y(this.t1,{borderCollapse:'collapse'})
this.lhs=$td(this.t1,0,0);this.main_head=$a(this.lhs,'h1','',def_ph_style.main_heading);this.sub_head=$a(this.lhs,'h4','',def_ph_style.sub_heading);this.separator=$a(this.wrapper,'div','',def_ph_style.separator);this.toolbar_area=$a(this.wrapper,'div','',def_ph_style.toolbar_area);this.padding_area=$a(this.wrapper,'div','',{padding:'3px'});$y($td(this.t1,0,1),{textAlign:'right',padding:'3px'});this.close_btn=$btn($td(this.t1,0,1),'Close',function(){nav_obj.show_last_open();},0);if(main_text)this.main_head.innerHTML=main_text;if(sub_text)this.sub_head.innerHTML=sub_text;this.buttons={};this.buttons2={};}
PageHeader.prototype.add_button=function(label,fn,bold,icon,green){var tb=this.toolbar_area;if(this.buttons[label])return;var btn=$btn(tb,label,fn,{marginRight:'4px'},(green?'green':''));if(bold)$y(btn,{fontWeight:'bold'});this.buttons[label]=btn;$ds(this.toolbar_area);return btn;}
PageHeader.prototype.clear_toolbar=function(){this.toolbar_area.innerHTML='';this.buttons={};}
PageHeader.prototype.make_buttonset=function(){$(this.toolbar_area).buttonset();}
var cur_autosug;function hide_autosuggest(){if(cur_autosug)cur_autosug.clearSuggestions();}
function AutoSuggest(id,param){this.fld=$i(id);if(!this.fld){return 0;alert('AutoSuggest: No ID');}
this.init();this.oP=param?param:{};var k,def={minchars:1,meth:"get",varname:"input",className:"autosuggest",timeout:4000,delay:1000,offsety:-5,shownoresults:true,noresults:"No results!",maxheight:250,cache:false,maxentries:25,fixed_options:false,xdelta:0,ydelta:5}
for(k in def)
{if(typeof(this.oP[k])!=typeof(def[k]))
this.oP[k]=def[k];}
var p=this;this.fld.onkeypress=function(ev){if(!(selector&&selector.display))return p.onKeyPress(ev);};this.fld.onkeyup=function(ev){if(!(selector&&selector.display))return p.onKeyUp(ev);};this.fld.setAttribute("autocomplete","off");};AutoSuggest.prototype.init=function(){this.sInp="";this.nInpC=0;this.aSug=[];this.iHigh=0;}
AutoSuggest.prototype.onKeyPress=function(ev)
{var key=(window.event)?window.event.keyCode:ev.keyCode;var RETURN=13;var TAB=9;var ESC=27;var bubble=1;switch(key)
{case TAB:this.setHighlightedValue();bubble=0;break;case RETURN:this.setHighlightedValue();bubble=0;break;case ESC:this.clearSuggestions();break;}
return bubble;}
AutoSuggest.prototype.onKeyUp=function(ev)
{var key=(window.event)?window.event.keyCode:ev.keyCode;var ARRUP=38;var ARRDN=40;var bubble=1;switch(key){case ARRUP:this.changeHighlight(key);bubble=0;break;case ARRDN:this.changeHighlight(key);bubble=0;break;default:if(key!=13){if(this.oP.fixed_options)
this.find_nearest(key);else
this.getSuggestions(this.fld.value);}}
return bubble;}
AutoSuggest.prototype.clear_user_inp=function(){this.user_inp='';}
AutoSuggest.prototype.find_nearest=function(key){var list=this.ul;var same_key=0;if(!list){if(this.aSug){this.createList(this.aSug);}if(this.aSug[0].value.substr(0,this.user_inp.length).toLowerCase()==String.fromCharCode(key)){this.resetTimeout();return;}}
if((this.user_inp.length==1)&&this.user_inp==String.fromCharCode(key).toLowerCase()){same_key=1;}else{this.user_inp+=String.fromCharCode(key).toLowerCase();}
window.clearTimeout(this.clear_timer);var st=this.iHigh;if(!same_key)st--;for(var i=st;i<this.aSug.length;i++){if(this.aSug[i].value.substr(0,this.user_inp.length).toLowerCase()==this.user_inp){this.setHighlight(i+1);this.resetTimeout();return;}}
this.clear_timer=window.setTimeout('if(cur_autosug)cur_autosug.clear_user_inp()',3000);for(var i=0;i<st;i++){if(this.aSug[i].value.substr(0,this.user_inp.length).toLowerCase()==this.user_inp){this.setHighlight(i+1);this.resetTimeout();return;}}}
AutoSuggest.prototype.getSuggestions=function(val)
{if(val==this.sInp)return 0;if(this.body&&this.body.parentNode)
this.body.parentNode.removeChild(this.body);this.sInp=val;if(val.length<this.oP.minchars)
{this.aSug=[];this.nInpC=val.length;return 0;}
var ol=this.nInpC;this.nInpC=val.length?val.length:0;var l=this.aSug.length;if(this.nInpC>ol&&l&&l<this.oP.maxentries&&this.oP.cache)
{var arr=[];for(var i=0;i<l;i++)
{if(this.aSug[i].value.substr(0,val.length).toLowerCase()==val.toLowerCase())
arr.push(this.aSug[i]);}
this.aSug=arr;this.createList(this.aSug);return false;}
else
{var me=this;var input=this.sInp;clearTimeout(this.ajID);this.ajID=setTimeout(function(){me.doAjaxRequest(input)},this.oP.delay);}
return false;};AutoSuggest.prototype.doAjaxRequest=function(input)
{if(input!=this.fld.value)
return false;var me=this;var q='';this.oP.link_field.set_get_query();if(this.oP.link_field.get_query){if(cur_frm)var doc=locals[cur_frm.doctype][cur_frm.docname];q=this.oP.link_field.get_query(doc,this.oP.link_field.doctype,this.oP.link_field.docname);}
this.fld.old_bg=this.fld.style.backgroundColor;$y(this.fld,{backgroundColor:'#FFC'});$c('webnotes.widgets.search.search_link',args={'txt':this.fld.value,'dt':this.oP.link_field.df.options,'query':q},function(r,rt){$y(me.fld,{backgroundColor:(me.fld.old_bg?me.fld.old_bg:'#FFF')});me.setSuggestions(r,rt,input);});return;};AutoSuggest.prototype.setSuggestions=function(r,rt,input)
{if(input!=this.fld.value)
return false;this.aSug=[];if(this.oP.json){var jsondata=eval('('+rt+')');if(jsondata){for(var i=0;i<jsondata.results.length;i++){this.aSug.push({'id':jsondata.results[i].id,'value':jsondata.results[i].value,'info':jsondata.results[i].info});}}}
this.createList(this.aSug);};AutoSuggest.prototype.createList=function(arr){if(cur_autosug&&cur_autosug!=this)
cur_autosug.clearSuggestions();this.aSug=arr;this.user_inp='';var me=this;var pos=objpos(this.fld);pos.y+=this.oP.ydelta;pos.x+=this.oP.xdelta;if(pos.x<=0||pos.y<=0)return;if(this.body&&this.body.parentNode)
this.body.parentNode.removeChild(this.body);this.killTimeout();if(arr.length==0&&!this.oP.shownoresults)
return false;var div=$ce("div",{className:this.oP.className});top_index++;div.style.zIndex=1100;div.isactive=1;this.ul=$ce("ul",{id:"as_ul"});var ul=this.ul;for(var i=0;i<arr.length;i++){var val=arr[i].value;if(this.oP.fixed_options){var output=val;}else{var st=val.toLowerCase().indexOf(this.sInp.toLowerCase());var output=val.substring(0,st)+"<em>"+val.substring(st,st+this.sInp.length)+"</em>"+val.substring(st+this.sInp.length);}
var span=$ce("span",{},output,true);span.isactive=1;if(arr[i].info!="")
{var small=$ce("small",{},arr[i].info);span.appendChild(small);small.isactive=1}
var a=$a(null,"a");a.appendChild(span);a.name=i+1;a.onclick=function(e){me.setHighlightedValue();};a.onmouseover=function(){me.setHighlight(this.name);};a.isactive=1;var li=$ce("li",{},a);if(!val){$y(span,{height:'12px'});}
ul.appendChild(li);}
if(arr.length==0&&this.oP.shownoresults){var li=$ce("li",{className:"as_warning"},this.oP.noresults);ul.appendChild(li);}
div.appendChild(ul);var mywid=cint(this.fld.offsetWidth);if(this.oP.fixed_options){mywid+=20;}
if(cint(mywid)<100)mywid=100;var left=pos.x-((mywid-this.fld.offsetWidth)/2);if(left<0){mywid=mywid+(left/2);left=0;}
div.style.left=left+"px";div.style.top=(pos.y+this.fld.offsetHeight+this.oP.offsety)+"px";div.style.width=mywid+'px';div.onmouseover=function(){me.killTimeout()};div.onmouseout=function(){me.resetTimeout()};popup_cont.appendChild(div);if(cint(div.clientHeight)>=this.oP.maxheight){div.original_height=cint(div.clientHeight);$y(div,{height:this.oP.maxheight+'px',overflowY:'auto'});div.scrollbars=true;}
this.body=div;if(isIE){$y(div,{border:'1px solid #444'});}
this.iHigh=0;if(!this.iHigh)
this.changeHighlight(40);this.resetTimeout();};AutoSuggest.prototype.changeHighlight=function(key)
{var list=this.ul;if(!list){if(this.aSug)
this.createList(this.aSug);return false;}
var n;if(key==40)
n=this.iHigh+1;else if(key==38)
n=this.iHigh-1;if(n>list.childNodes.length)
n=list.childNodes.length;if(n<1)
n=1;this.setHighlight(n);};AutoSuggest.prototype.setHighlight=function(n)
{this.resetTimeout();var list=this.ul;if(!list)
return false;if(this.iHigh>0)
this.clearHighlight();this.iHigh=Number(n);var ele=list.childNodes[this.iHigh-1];ele.className="as_highlight";if(this.body.scrollbars){var cur_y=0;for(var i=0;i<this.iHigh-1;i++)
cur_y+=(isIE?list.childNodes[i].offsetHeight:list.childNodes[i].clientHeight);if(cur_y<this.body.scrollTop)
this.body.scrollTop=cur_y;ff_delta=(isFF?cint(this.iHigh/2):0);var h=(isIE?ele.offsetHeight:ele.clientHeight);if(cur_y>=(this.body.scrollTop+this.oP.maxheight-h))
this.body.scrollTop=cur_y-this.oP.maxheight+h+ff_delta;}
if(!this.aSug[this.iHigh-1])return;};AutoSuggest.prototype.clearHighlight=function()
{var list=this.ul;if(!list)
return false;if(this.iHigh>0){list.childNodes[this.iHigh-1].className="";this.iHigh=0;}};AutoSuggest.prototype.setHighlightedValue=function()
{if(this.iHigh){this.sInp=this.aSug[this.iHigh-1].value;if(this.set_input_value){this.set_input_value(this.sInp);}else{this.fld.value=this.sInp;}
this.clearSuggestions();this.killTimeout();if(this.fld.onchange){cur_autosug=null;this.fld.onchange();}}};AutoSuggest.prototype.killTimeout=function(){cur_autosug=this;clearTimeout(this.toID);clearTimeout(this.clear_timer);};AutoSuggest.prototype.resetTimeout=function(){cur_autosug=this;clearTimeout(this.toID);clearTimeout(this.clear_timer);this.toID=setTimeout(function(){if(cur_autosug)cur_autosug.clearSuggestions(1);},this.oP.timeout);};AutoSuggest.prototype.clearSuggestions=function(from_timeout){this.killTimeout();cur_autosug=null;var me=this;if(this.body){$dh(this.body);delete this.body;}
if(!this.ul)return;if(this.ul)
delete this.ul;this.iHigh=0;if(from_timeout&&this.fld.field_object&&!this.oP.fixed_options){if(this.fld.onchange)this.fld.onchange();}}
$ce=function(type,attr,cont,html)
{var ne=document.createElement(type);if(!ne)return 0;for(var a in attr)ne[a]=attr[a];var t=typeof(cont);if(t=="string"&&!html)ne.appendChild(document.createTextNode(cont));else if(t=="string"&&html)ne.innerHTML=cont;else if(t=="object")ne.appendChild(cont);return ne;};function SelectWidget(parent,options,width,editable,bg_color){var me=this;this.inp=$a(parent,'select');if(options)add_sel_options(this.inp,options);if(width)$y(this.inp,{width:width});this.set_width=function(w){$y(this.inp,{width:w})};this.set_options=function(o){add_sel_options(this.inp,o);}
this.inp.onchange=function(){if(me.onchange)me.onchange(this);}
return;}
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
ListSelector=function(title,intro,list,onupdate,selectable){var me=this;this.list=list;this.selectable=selectable;this.dialog=new Dialog(400,600,title);this.items=[];if(intro){intro_area=$a(this.dialog.body,'div','help_box',{margin:'16px',marginBottom:'0px',width:'312px'});intro_area.innerHTML=intro;}
this.body=$a(this.dialog.body,'div','',{margin:'16px',position:'relative'});this.render();var btn=$btn(this.dialog.body,'Update',function(){me.update()},{margin:'0px 0px 16px 16px'},'green',1);this.update=function(){if(me.selected_item)$bg(me.selected_item,'#FFF');var ret=[];for(var i=0;i<me.items.length;i++){ret.push([me.items[i].label,me.items[i].idx,(me.items[i].check?(me.items[i].check.checked?1:0):0),me.items[i].det]);}
me.dialog.hide();onupdate(ret);}
this.dialog.show();}
ListSelector.prototype.render=function(to_hide){this.body.innerHTML='';this.items=[];this.list.sort(function(a,b){return a[1]>b[1];});for(i=0;i<this.list.length;i++){this.list[i][1]=i;this.items.push(new ListSelectorItem(this,this.list[i],i));if(i==to_hide)$dh(this.items[i].body);}}
ListSelector.prototype.insert_at=function(item,new_idx){for(var i=0;i<this.list.length;i++){if(this.list[i][1]>=new_idx)this.list[i][1]++;}
for(var i=0;i<this.list.length;i++){if(this.list[i][1]>=item.idx)this.list[i][1]--;}
this.list[item.idx][1]=new_idx;var n=new_idx-((new_idx>item.idx)?1:0);this.render(n);this.items[n].body.onmousedown();$(this.items[n].body).slideDown();}
ListSelectorItem=function(ls,det,idx){this.det=det;this.ls=ls;this.idx=idx;this.body=$a(ls.body,'div','',{padding:'8px',margin:'4px 0px',border:'1px solid #AAA',position:'relative',width:'320px',height:'14px',cursor:'move'});if(ls.selectable){this.make_with_checkbox();}else{this.body.innerHTML=det[0];}
this.set_drag();}
ListSelectorItem.prototype.make_with_checkbox=function(){this.body.tab=make_table(this.body,1,2,null,['28px',null],{verticalAlign:'top'});this.check=$a_input($td(this.body.tab,0,0),'checkbox');if(this.det[2])this.check.checked=1;$td(this.body.tab,0,1).innerHTML=this.det[0];}
ListSelectorItem.prototype.set_drag=function(){var me=this;this.body.item=this;this.body.onmousedown=function(){$bg(this,'#FFC');if(me.ls.selected_item&&me.ls.selected_item!=this)$bg(me.ls.selected_item,'#FFF');me.ls.selected_item=this;}
$(this.body).draggable({opacity:0.6,helper:'clone',containment:'parent',scroll:false,cursor:'move',drag:function(event,ui){me.ls.drag_item=this.item;}});$(this.body).droppable({drop:function(event,ui){me.ls.insert_at(me.ls.drag_item,me.idx+(me.ls.drag_item.idx<me.idx?1:0));}});}
var no_value_fields=['Section Break','Column Break','HTML','Table','FlexTable','Button','Image'];var codeid=0;var code_editors={};function Field(){this.with_label=1;}
Field.prototype.make_body=function(){var ischk=(this.df.fieldtype=='Check'?1:0);if(this.parent)
this.wrapper=$a(this.parent,'div');else
this.wrapper=document.createElement('div');this.label_area=$a(this.wrapper,'div','',{margin:'8px 0px 2px 0px'});if(ischk&&!this.in_grid){this.input_area=$a(this.label_area,'span','',{marginRight:'4px'});this.disp_area=$a(this.label_area,'span','',{marginRight:'4px'});}
if(this.with_label){this.label_span=$a(this.label_area,'span','field_label')
this.label_icon=$a(this.label_area,'img','',{margin:'-3px 4px -3px 4px'});$dh(this.label_icon);this.label_icon.src='images/icons/error.gif';this.label_icon.title='Mandatory value needs to be entered';this.suggest_icon=$a(this.label_area,'img','',{margin:'-3px 4px -3px 0px'});$dh(this.suggest_icon);this.suggest_icon.src='images/icons/bullet_arrow_down.png';this.suggest_icon.title='With suggestions';}else{this.label_span=$a(this.label_area,'span','',{marginRight:'4px'})
$dh(this.label_area);}
if(!this.input_area){this.input_area=$a(this.wrapper,'div');this.disp_area=$a(this.wrapper,'div');}
if(this.in_grid){if(this.label_area)$dh(this.label_area);}else{this.input_area.className='input_area';$y(this.wrapper,{marginBottom:'4px'});this.set_description();}
if(this.onmake)this.onmake();}
Field.prototype.set_max_width=function(){var no_max=['Code','Text Editor','Text','Table','HTML']
if(this.wrapper&&this.layout_cell&&this.layout_cell.parentNode.cells&&this.layout_cell.parentNode.cells.length==1&&!in_list(no_max,this.df.fieldtype)){$y(this.wrapper,{paddingRight:'50%'});}}
Field.prototype.set_label=function(){if(this.with_label&&this.label_area&&this.label!=this.df.label){this.label_span.innerHTML=this.df.label;this.label=this.df.label;}}
Field.prototype.set_description=function(){if(this.df.description){var p=in_list(['Text Editor','Code','Check'],this.df.fieldtype)?this.label_area:this.wrapper;this.desc_area=$a(p,'div','field_description','',this.df.description)
if(in_list(['Text Editor','Code'],this.df.fieldtype))
$(this.desc_area).addClass('field_description_top');}}
Field.prototype.get_status=function(){if(this.in_filter)this.not_in_form=this.in_filter;if(this.not_in_form){return'Write';}
var fn=this.df.fieldname?this.df.fieldname:this.df.label;this.df=get_field(this.doctype,fn,this.docname);if(!this.df.permlevel)this.df.permlevel=0;var p=this.perm[this.df.permlevel];var ret;if(cur_frm.editable&&p&&p[WRITE])ret='Write';else if(p&&p[READ])ret='Read';else ret='None';if(this.df.fieldtype=='Binary')
ret='None';if(cint(this.df.hidden))
ret='None';if(ret=='Write'&&cint(cur_frm.doc.docstatus)>0)ret='Read';var a_o_s=cint(this.df.allow_on_submit);if(a_o_s&&(this.in_grid||(this.frm&&this.frm.not_in_container))){a_o_s=null;if(this.in_grid)a_o_s=this.grid.field.df.allow_on_submit;if(this.frm&&this.frm.not_in_container){a_o_s=cur_grid.field.df.allow_on_submit;}}
if(cur_frm.editable&&a_o_s&&cint(cur_frm.doc.docstatus)>0&&!this.df.hidden){tmp_perm=get_perm(cur_frm.doctype,cur_frm.docname,1);if(tmp_perm[this.df.permlevel]&&tmp_perm[this.df.permlevel][WRITE])ret='Write';}
return ret;}
Field.prototype.set_style_mandatory=function(add){if(add){$(this.txt?this.txt:this.input).addClass('input-mandatory');if(this.disp_area)$(this.disp_area).addClass('input-mandatory');}else{$(this.txt?this.txt:this.input).removeClass('input-mandatory');if(this.disp_area)$(this.disp_area).removeClass('input-mandatory');}}
Field.prototype.refresh_mandatory=function(){if(this.in_filter)return;if(this.df.reqd){if(this.label_area)this.label_area.style.color="#d22";this.set_style_mandatory(1);}else{if(this.label_area)this.label_area.style.color="#222";this.set_style_mandatory(0);}
this.refresh_label_icon()
this.set_reqd=this.df.reqd;}
Field.prototype.refresh_display=function(){if(!this.set_status||this.set_status!=this.disp_status){if(this.disp_status=='Write'){if(this.make_input&&(!this.input)){this.make_input();if(this.onmake_input)this.onmake_input();}
if(this.show)this.show()
else{$ds(this.wrapper);}
if(this.input){$ds(this.input_area);$dh(this.disp_area);if(this.input.refresh)this.input.refresh();}else{$dh(this.input_area);$ds(this.disp_area);}}else if(this.disp_status=='Read'){if(this.show)this.show()
else{$ds(this.wrapper);}
$dh(this.input_area);$ds(this.disp_area);}else{if(this.hide)this.hide();else $dh(this.wrapper);}
this.set_status=this.disp_status;}}
Field.prototype.refresh=function(){this.disp_status=this.get_status();if(this.in_grid&&this.table_refresh&&this.disp_status=='Write')
{this.table_refresh();return;}
this.set_label();this.refresh_display();if(this.onrefresh)this.onrefresh();if(this.input&&this.input.refresh)this.input.refresh(this.df);if(!this.not_in_form)
this.set_input(_f.get_value(this.doctype,this.docname,this.df.fieldname));this.refresh_mandatory();this.set_max_width();}
Field.prototype.refresh_label_icon=function(){if(this.df.reqd){if(this.get_value&&is_null(this.get_value())){if(this.label_icon)$ds(this.label_icon);$(this.txt?this.txt:this.input).addClass('field-to-update')}else{if(this.label_icon)$dh(this.label_icon);$(this.txt?this.txt:this.input).removeClass('field-to-update')}}}
Field.prototype.set=function(val){if(this.not_in_form)
return;if((!this.docname)&&this.grid){this.docname=this.grid.add_newrow();}
if(in_list(['Data','Text','Small Text','Code'],this.df.fieldtype))
val=clean_smart_quotes(val);var set_val=val;if(this.validate)set_val=this.validate(val);_f.set_value(this.doctype,this.docname,this.df.fieldname,set_val);this.value=val;}
Field.prototype.set_input=function(val){this.value=val;if(this.input&&this.input.set_input){if(val==null)this.input.set_input('');else this.input.set_input(val);}
var disp_val=val;if(val==null)disp_val='';this.set_disp(disp_val);}
Field.prototype.run_trigger=function(){this.refresh_label_icon();if(this.df.reqd&&this.get_value&&!is_null(this.get_value())&&this.set_as_error)
this.set_as_error(0);if(this.not_in_form){return;}
if(cur_frm.cscript[this.df.fieldname])
cur_frm.runclientscript(this.df.fieldname,this.doctype,this.docname);cur_frm.refresh_dependency();}
Field.prototype.set_disp_html=function(t){if(this.disp_area){$(this.disp_area).addClass('disp_area');this.disp_area.innerHTML=(t==null?'':t);if(!t)$(this.disp_area).addClass('disp_area_no_val');}}
Field.prototype.set_disp=function(val){this.set_disp_html(val);}
Field.prototype.set_as_error=function(set){if(this.in_grid||this.in_filter)return;var w=this.txt?this.txt:this.input;if(set){$y(w,{border:'2px solid RED'});}else{$y(w,{border:'1px solid #888'});}}
Field.prototype.activate=function(docname){this.docname=docname;this.refresh();if(this.input){this.input.isactive=true;var v=_f.get_value(this.doctype,this.docname,this.df.fieldname);this.last_value=v;if(this.input.onchange&&this.input.get_value&&this.input.get_value()!=v){if(this.validate)
this.input.set_value(this.validate(v));else
this.input.set_value((v==null)?'':v);if(this.format_input)
this.format_input();}
if(this.input.focus){try{this.input.focus();}catch(e){}}}
if(this.txt){try{this.txt.focus();}catch(e){}
this.txt.isactive=true;if(this.btn)this.btn.isactive=true;this.txt.field_object=this;}}
function DataField(){}DataField.prototype=new Field();DataField.prototype.make_input=function(){var me=this;this.input=$a(this.input_area,'input');if(this.df.fieldtype=='Password'){if(isIE){this.input_area.innerHTML='<input type="password">';this.input=this.input_area.childNodes[0];}else{this.input.setAttribute('type','password');}}
this.get_value=function(){var v=this.input.value;if(this.validate)v=this.validate(v);return v;}
this.input.name=this.df.fieldname;this.input.onchange=function(){if(!me.last_value)me.last_value='';if(me.validate)
me.input.value=me.validate(me.input.value);me.set(me.input.value);if(me.format_input)
me.format_input();if(in_list(['Currency','Float','Int'],me.df.fieldtype)){if(flt(me.last_value)==flt(me.input.value)){me.last_value=me.input.value;return;}}
me.last_value=me.input.value;me.run_trigger();}
this.input.set_input=function(val){if(val==null)val='';me.input.value=val;if(me.format_input)me.format_input();}
if(this.df.options=='Suggest'){if(this.suggest_icon)$di(this.suggest_icon);this.set_get_query=function(){}
this.get_query=function(doc,dt,dn){return repl('SELECT DISTINCT `%(fieldname)s` FROM `tab%(dt)s` WHERE `%(fieldname)s` LIKE "%s" LIMIT 50',{fieldname:me.df.fieldname,dt:me.df.parent})}
var opts={script:'',json:true,maxresults:10,link_field:this};this.as=new AutoSuggest(this.input,opts);}}
DataField.prototype.validate=function(v){if(this.df.options=='Phone'){if(v+''=='')return'';v1=''
v=v.replace(/ /g,'').replace(/-/g,'').replace(/\(/g,'').replace(/\)/g,'');if(v&&v.substr(0,1)=='+'){v1='+';v=v.substr(1);}
if(v&&v.substr(0,2)=='00'){v1+='00';v=v.substr(2);}
if(v&&v.substr(0,1)=='0'){v1+='0';v=v.substr(1);}
v1+=cint(v)+'';return v1;}else if(this.df.options=='Email'){if(v+''=='')return'';if(!validate_email(v)){msgprint(this.df.label+': '+v+' is not a valid email id');return'';}else
return v;}else{return v;}}
DataField.prototype.onrefresh=function(){if(this.input&&this.df.colour){var col='#'+this.df.colour.split(':')[1];$bg(this.input,col);}}
function ReadOnlyField(){}
ReadOnlyField.prototype=new Field();function HTMLField(){}
HTMLField.prototype=new Field();HTMLField.prototype.with_label=0;HTMLField.prototype.set_disp=function(val){this.disp_area.innerHTML=val;}
HTMLField.prototype.set_input=function(val){if(val)this.set_disp(val);}
HTMLField.prototype.onrefresh=function(){this.set_disp(this.df.options?this.df.options:'');}
var datepicker_active=0;function DateField(){}DateField.prototype=new Field();DateField.prototype.make_input=function(){var me=this;this.user_fmt=locals['Control Panel']['Control Panel'].date_format;if(!this.user_fmt)this.user_fmt='dd-mm-yy';this.input=$a(this.input_area,'input');$(this.input).datepicker({dateFormat:me.user_fmt.replace('yyyy','yy'),altFormat:'yy-mm-dd',changeYear:true,beforeShow:function(input,inst){datepicker_active=1},onClose:function(dateText,inst){datepicker_active=0;if(_f.cur_grid_cell)
_f.cur_grid_cell.grid.cell_deselect();}});var me=this;me.input.onchange=function(){if(this.value==null)this.value='';if(!this.not_in_form)
me.set(dateutil.user_to_str(me.input.value));me.run_trigger();}
me.input.set_input=function(val){if(val==null)val='';else val=dateutil.str_to_user(val);me.input.value=val;}
me.get_value=function(){if(me.input.value)
return dateutil.user_to_str(me.input.value);}}
DateField.prototype.set_disp=function(val){var v=dateutil.str_to_user(val);if(v==null)v='';this.set_disp_html(v);}
DateField.prototype.validate=function(v){if(!v)return;var me=this;this.clear=function(){msgprint("Date must be in format "+this.user_fmt);me.input.set_input('');return'';}
var t=v.split('-');if(t.length!=3){return this.clear();}
else if(cint(t[1])>12||cint(t[1])<1){return this.clear();}
else if(cint(t[2])>31||cint(t[2])<1){return this.clear();}
return v;};var _link_onchange_flag=null;function LinkField(){}LinkField.prototype=new Field();LinkField.prototype.make_input=function(){var me=this;if(me.df.no_buttons){this.txt=$a(this.input_area,'input');this.input=this.txt;}else{makeinput_popup(this,'ic-zoom','ic-sq_next','ic-sq_plus');me.setup_buttons();me.onrefresh=function(){if(me.can_create&&cur_frm.doc.docstatus==0)$ds(me.btn2);else $dh(me.btn2);}}
me.txt.field_object=this;me.set_onchange();me.input.set_input=function(val){if(val==undefined)val='';me.txt.value=val;}
me.get_value=function(){return me.txt.value;}
var opts={script:'',json:true,maxresults:10,link_field:me};this.as=new AutoSuggest(me.txt,opts);}
LinkField.prototype.setup_buttons=function(){var me=this;me.btn.onclick=function(){selector.set(me,me.df.options,me.df.label);selector.show(me.txt);}
if(me.btn1)me.btn1.onclick=function(){if(me.txt.value&&me.df.options){loaddoc(me.df.options,me.txt.value);}}
me.can_create=0;if((!me.not_in_form)&&in_list(profile.can_create,me.df.options)){me.can_create=1;me.btn2.onclick=function(){var on_save_callback=function(new_rec){if(new_rec){var d=_f.calling_doc_stack.pop();locals[d[0]][d[1]][me.df.fieldname]=new_rec;me.refresh();if(me.grid)me.grid.refresh();me.run_trigger();}}
_f.calling_doc_stack.push([me.doctype,me.docname]);new_doc(me.df.options,me.on_new,1,on_save_callback,me.doctype,me.docname,me.frm.not_in_container);}}else{$dh(me.btn2);$y($td(me.tab,0,2),{width:'0px'});}}
LinkField.prototype.set_onchange=function(){var me=this;me.txt.onchange=function(e){if(cur_autosug)return;if(_link_onchange_flag){return;}
_link_onchange_flag=1;me.refresh_label_icon();if(me.not_in_form){_link_onchange_flag=0;return;}
if(cur_frm){if(me.txt.value==locals[me.doctype][me.docname][me.df.fieldname]){me.set(me.txt.value);me.run_trigger();setTimeout('_link_onchange_flag = 0',500);return;}}
me.set(me.txt.value);if(_f.cur_grid_cell)
_f.cur_grid_cell.grid.cell_deselect();if(!me.txt.value){me.run_trigger();setTimeout('_link_onchange_flag = 0',500);return;}
var fetch='';if(cur_frm.fetch_dict[me.df.fieldname])
fetch=cur_frm.fetch_dict[me.df.fieldname].columns.join(', ');$c('webnotes.widgets.form.validate_link',{'value':me.txt.value,'options':me.df.options,'fetch':fetch},function(r,rt){setTimeout('_link_onchange_flag = 0',500);if(selector&&selector.display)return;if(r.message=='Ok'){if(r.fetch_values)me.set_fetch_values(r.fetch_values);me.run_trigger();}else{var astr='';if(in_list(profile.can_create,me.df.options))astr=repl('<br><br><span class="link_type" onclick="newdoc(\'%(dt)s\')">Click here</span> to create a new %(dtl)s',{dt:me.df.options,dtl:get_doctype_label(me.df.options)})
msgprint(repl('error:<b>%(val)s</b> is not a valid %(dt)s.<br><br>You must first create a new %(dt)s <b>%(val)s</b> and then select its value. To find an existing %(dt)s, click on the magnifying glass next to the field.%(add)s',{val:me.txt.value,dt:get_doctype_label(me.df.options),add:astr}));me.txt.value='';me.set('');}});}}
LinkField.prototype.set_fetch_values=function(fetch_values){var fl=cur_frm.fetch_dict[this.df.fieldname].fields;var changed_fields=[];for(var i=0;i<fl.length;i++){if(locals[this.doctype][this.docname][fl[i]]!=fetch_values[i]){locals[this.doctype][this.docname][fl[i]]=fetch_values[i];if(!this.grid){refresh_field(fl[i]);changed_fields.push(fl[i]);}}}
for(i=0;i<changed_fields.length;i++){if(cur_frm.fields_dict[changed_fields[i]])
cur_frm.fields_dict[changed_fields[i]].run_trigger();}
if(this.grid)this.grid.refresh();}
LinkField.prototype.set_get_query=function(){if(this.get_query)return;if(this.grid){var f=this.grid.get_field(this.df.fieldname);if(f.get_query)this.get_query=f.get_query;}}
LinkField.prototype.set_disp=function(val){var t=null;if(val)t="<a href=\'javascript:loaddoc(\""+this.df.options+"\", \""+val+"\")\'>"+val+"</a>";this.set_disp_html(t);}
function IntField(){}IntField.prototype=new DataField();IntField.prototype.validate=function(v){if(isNaN(parseInt(v)))return null;return cint(v);};IntField.prototype.format_input=function(){if(this.input.value==null)this.input.value='';}
function FloatField(){}FloatField.prototype=new DataField();FloatField.prototype.validate=function(v){var v=parseFloat(v);if(isNaN(v))return null;return v;};FloatField.prototype.format_input=function(){if(this.input.value==null)this.input.value='';}
function CurrencyField(){}CurrencyField.prototype=new DataField();CurrencyField.prototype.format_input=function(){var v=fmt_money(this.input.value);if(this.not_in_form){if(!flt(this.input.value))v='';}
this.input.value=v;}
CurrencyField.prototype.validate=function(v){if(v==null||v=='')
return 0;return flt(v,2);}
CurrencyField.prototype.set_disp=function(val){var v=fmt_money(val);this.set_disp_html(v);}
CurrencyField.prototype.onmake_input=function(){if(!this.input)return;this.input.onfocus=function(){if(flt(this.value)==0)this.select();}}
function CheckField(){}CheckField.prototype=new Field();CheckField.prototype.validate=function(v){var v=parseInt(v);if(isNaN(v))return 0;return v;};CheckField.prototype.onmake=function(){this.checkimg=$a(this.disp_area,'div');var img=$a(this.checkimg,'img');img.src='images/ui/tick.gif';$dh(this.checkimg);}
CheckField.prototype.make_input=function(){var me=this;this.input=$a_input(this.input_area,'checkbox');$y(this.input,{width:"16px",border:'0px',margin:'2px'});this.input.onchange=function(){me.set(this.checked?1:0);me.run_trigger();}
if(isIE){this.input.onclick=this.input.onchange;$y(this.input,{margin:'-1px'});}
this.input.set_input=function(v){v=parseInt(v);if(isNaN(v))v=0;if(v)me.input.checked=true;else me.input.checked=false;}
this.get_value=function(){return this.input.checked?1:0;}}
CheckField.prototype.set_disp=function(val){if(val){$ds(this.checkimg);}
else{$dh(this.checkimg);}}
function TextField(){}TextField.prototype=new Field();TextField.prototype.set_disp=function(val){this.disp_area.innerHTML=replace_newlines(val);}
TextField.prototype.make_input=function(){var me=this;if(this.in_grid)
return;this.input=$a(this.input_area,'textarea');this.input.wrap='off';if(this.df.fieldtype=='Small Text')
this.input.style.height="80px";this.input.set_input=function(v){me.input.value=v;}
this.input.onchange=function(){me.set(me.input.value);me.run_trigger();}
this.get_value=function(){return this.input.value;}}
var text_dialog;function make_text_dialog(){var d=new Dialog(520,410,'Edit Text');d.make_body([['Text','Enter Text'],['HTML','Description'],['Button','Update']]);d.widgets['Update'].onclick=function(){var t=this.dialog;t.field.set(t.widgets['Enter Text'].value);t.hide();}
d.onshow=function(){this.widgets['Enter Text'].style.height='300px';var v=_f.get_value(this.field.doctype,this.field.docname,this.field.df.fieldname);this.widgets['Enter Text'].value=v==null?'':v;this.widgets['Enter Text'].focus();this.widgets['Description'].innerHTML=''
if(this.field.df.description)
$a(this.widgets['Description'],'div','field_description','',this.field.df.description);}
d.onhide=function(){if(_f.cur_grid_cell)
_f.cur_grid_cell.grid.cell_deselect();}
text_dialog=d;}
TextField.prototype.table_refresh=function(){if(!this.text_dialog)
make_text_dialog();text_dialog.set_title('Enter text for "'+this.df.label+'"');text_dialog.field=this;text_dialog.show();}
function SelectField(){}SelectField.prototype=new Field();SelectField.prototype.make_input=function(){var me=this;var opt=[];if(this.in_filter&&(!this.df.single_select)){this.input=$a(this.input_area,'select');this.input.multiple=true;this.input.style.height='4em';this.input.lab=$a(this.input_area,'div',{fontSize:'9px',color:'#999'});this.input.lab.innerHTML='(Use Ctrl+Click to select multiple or de-select)'}else{this.input=$a(this.input_area,'select');this.input.onchange=function(){if(me.validate)
me.validate();me.set(sel_val(this));if(isIE&&me.in_grid){$dh(_f.cur_grid_cell.grid.wrapper);$ds(_f.cur_grid_cell.grid.wrapper);}
me.run_trigger();}}
this.set_as_single=function(){var i=this.input;i.multiple=false;i.style.height=null;if(i.lab)$dh(i.lab)}
this.refresh_options=function(options){if(options)
me.df.options=options;me.options_list=me.df.options?me.df.options.split('\n'):[];empty_select(this.input);if(me.in_filter&&me.options_list[0]!=''){me.options_list=add_lists([''],me.options_list);}
add_sel_options(this.input,me.options_list);}
this.onrefresh=function(){this.refresh_options();if(this.not_in_form){this.input.value='';return;}
if(_f.get_value)
var v=_f.get_value(this.doctype,this.docname,this.df.fieldname);else{if(this.options_list&&this.options_list.length)
var v=this.options_list[0];else
var v=null;}
this.input.set_input(v);}
this.input.set_input=function(v){if(!v){if(!me.input.multiple){if(me.docname){if(me.options_list&&me.options_list.length){me.set(me.options_list[0]);me.input.value=me.options_list[0];}else{me.input.value='';}}}}else{if(me.options_list&&in_list(me.options_list,v)){if(me.input.multiple){for(var i=0;i<me.input.options.length;i++){me.input.options[i].selected=0;if(me.input.options[i].value&&me.input.options[i].value==v)
me.input.options[i].selected=1;}}else{me.input.value=v;}}}}
this.get_value=function(){if(me.input.multiple){var l=[];for(var i=0;i<me.input.options.length;i++){if(me.input.options[i].selected)l[l.length]=me.input.options[i].value;}
return l;}else{if(me.input.options){var val=sel_val(me.input);if(!val&&!me.input.selectedIndex)
val=me.input.options[0].value;return val;}
return me.input.value;}}
this.refresh();}
function TimeField(){}TimeField.prototype=new Field();TimeField.prototype.get_time=function(){return time_to_hhmm(sel_val(this.input_hr),sel_val(this.input_mn),sel_val(this.input_am));}
TimeField.prototype.set_time=function(v){ret=time_to_ampm(v);this.input_hr.inp.value=ret[0];this.input_mn.inp.value=ret[1];this.input_am.inp.value=ret[2];}
TimeField.prototype.set_style_mandatory=function(){}
TimeField.prototype.set_as_error=function(){}
TimeField.prototype.make_input=function(){var me=this;this.input=$a(this.input_area,'div','time_field');var t=make_table(this.input,1,3,'160px');var opt_hr=['1','2','3','4','5','6','7','8','9','10','11','12'];var opt_mn=['00','05','10','15','20','25','30','35','40','45','50','55'];var opt_am=['AM','PM'];this.input_hr=new SelectWidget($td(t,0,0),opt_hr,'40px');this.input_mn=new SelectWidget($td(t,0,1),opt_mn,'40px');this.input_am=new SelectWidget($td(t,0,2),opt_am,'40px');this.input_hr.inp.isactive=1;this.input_mn.inp.isactive=1;this.input_am.inp.isactive=1;if(this.input_hr.btn){this.input_hr.btn.isactive=1;this.input_mn.btn.isactive=1;this.input_am.btn.isactive=1;}
var onchange_fn=function(){me.set(me.get_time());me.run_trigger();}
this.input_hr.inp.onchange=onchange_fn;this.input_mn.inp.onchange=onchange_fn;this.input_am.inp.onchange=onchange_fn;this.onrefresh=function(){var v=_f.get_value?_f.get_value(me.doctype,me.docname,me.df.fieldname):null;me.set_time(v);if(!v)
me.set(me.get_time());}
this.input.set_input=function(v){if(v==null)v='';me.set_time(v);}
this.get_value=function(){return this.get_time();}
this.refresh();}
TimeField.prototype.set_disp=function(v){var t=time_to_ampm(v);var t=t[0]+':'+t[1]+' '+t[2];this.set_disp_html(t);}
function makeinput_popup(me,iconsrc,iconsrc1,iconsrc2){me.input=$a(me.input_area,'div');if(!me.not_in_form)
$y(me.input,{width:'80%'});me.input.set_width=function(w){$y(me.input,{width:(w-2)+'px'});}
var tab=$a(me.input,'table');me.tab=tab;$y(tab,{width:'100%',borderCollapse:'collapse',tableLayout:'fixed'});var c0=tab.insertRow(0).insertCell(0);var c1=tab.rows[0].insertCell(1);$y(c1,{width:'20px'});me.txt=$a($a($a(c0,'div','',{paddingRight:'8px'}),'div'),'input','',{width:'100%'});me.btn=$a(c1,'div','wn-icon '+iconsrc,{width:'16px'});if(iconsrc1)
me.btn.setAttribute('title','Search');else
me.btn.setAttribute('title','Select Date');if(iconsrc1){var c2=tab.rows[0].insertCell(2);$y(c2,{width:'20px'});me.btn1=$a(c2,'div','wn-icon '+iconsrc1,{width:'16px'});me.btn1.setAttribute('title','Open Link');}
if(iconsrc2){var c3=tab.rows[0].insertCell(3);$y(c3,{width:'20px'});me.btn2=$a(c3,'div','wn-icon '+iconsrc2,{width:'16px'});me.btn2.setAttribute('title','Create New');$dh(me.btn2);}
if(me.df.colour)
me.txt.style.background='#'+me.df.colour.split(':')[1];me.txt.name=me.df.fieldname;me.setdisabled=function(tf){me.txt.disabled=tf;}}
var tmpid=0;function make_field(docfield,doctype,parent,frm,in_grid,hide_label){switch(docfield.fieldtype.toLowerCase()){case'data':var f=new DataField();break;case'password':var f=new DataField();break;case'int':var f=new IntField();break;case'float':var f=new FloatField();break;case'currency':var f=new CurrencyField();break;case'read only':var f=new ReadOnlyField();break;case'link':var f=new LinkField();break;case'date':var f=new DateField();break;case'time':var f=new TimeField();break;case'html':var f=new HTMLField();break;case'check':var f=new CheckField();break;case'text':var f=new TextField();break;case'small text':var f=new TextField();break;case'select':var f=new SelectField();break;case'code':var f=new _f.CodeField();break;case'text editor':var f=new _f.CodeField();break;case'button':var f=new _f.ButtonField();break;case'table':var f=new _f.TableField();break;case'section break':var f=new _f.SectionBreak();break;case'column break':var f=new _f.ColumnBreak();break;case'image':var f=new _f.ImageField();break;}
f.parent=parent;f.doctype=doctype;f.df=docfield;f.perm=frm?frm.perm:[[1,1,1]];if(_f)
f.col_break_width=_f.cur_col_break_width;if(in_grid){f.in_grid=true;f.with_label=0;}
if(hide_label){f.with_label=0;}
if(frm){f.frm=frm;if(parent)
f.layout_cell=parent.parentNode;}
if(f.init)f.init();f.make_body();return f;}
var about_dialog;function WNToolbar(parent){var me=this;this.setup=function(){this.wrapper=$a(parent,'div','',{color:'#FFF',padding:'2px 0px'});set_gradient(this.wrapper,'#444','#000');this.table_wrapper=$a(this.wrapper,'div','',{marginLeft:'4px',padding:'2px'});this.body_tab=make_table(this.table_wrapper,1,3,'100%',['0%','64%','36%'],{verticalAlign:'middle'});this.menu=new MenuToolbar($td(this.body_tab,0,1));this.setup_home();this.setup_new();this.setup_search();this.setup_recent();if(in_list(user_roles,'Administrator'))
this.setup_options();this.setup_help();this.setup_report_builder();this.setup_logout();}
this.setup_options=function(){var tm=this.menu.add_top_menu('Pages',function(){},"sprite-pages");var fn=function(){if(this.dt=='Page')
loadpage(this.dn);else
loaddoc(this.dt,this.dn);mclose();}
profile.start_items.sort(function(a,b){return(a[4]-b[4])});for(var i=0;i<profile.start_items.length;i++){var d=profile.start_items[i];var mi=this.menu.add_item('Pages',d[1],fn);mi.dt=d[0];mi.dn=d[5]?d[5]:d[1];}}
this.setup_home=function(){me.menu.add_top_menu('Home',function(){loadpage(home_page);},"sprite-home");}
this.setup_recent=function(){this.rdocs=me.menu.add_top_menu('Recent',function(){},"sprite-recent");this.rdocs.items={};var fn=function(){loaddoc(this.dt,this.dn);mclose();}
this.rdocs.add=function(dt,dn,on_top){var has_parent=false;if(locals[dt]&&locals[dt][dn]&&locals[dt][dn].parent)has_parent=true;if(!in_list(['Start Page','ToDo Item','Event','Search Criteria'],dt)&&!has_parent){if(this.items[dt+'-'+dn]){var mi=this.items[dt+'-'+dn];mi.bring_to_top();return;}
var tdn=dn;var rec_label='<table style="width: 100%" cellspacing=0><tr>'
+'<td style="width: 10%; vertical-align: middle;"><div class="status_flag" id="rec_'+dt+'-'+dn+'"></div></td>'
+'<td style="width: 50%; text-decoration: underline; color: #22B; padding: 2px;">'+tdn+'</td>'
+'<td style="font-size: 11px;">'+get_doctype_label(dt)+'</td></tr></table>';var mi=me.menu.add_item('Recent',rec_label,fn,on_top);mi.dt=dt;mi.dn=dn;this.items[dt+'-'+dn]=mi;if(pscript.on_recent_update)pscript.on_recent_update();}}
this.rdocs.remove=function(dt,dn){var it=me.rdocs.items[dt+'-'+dn];if(it)$dh(it);if(pscript.on_recent_update)pscript.on_recent_update();}
this.rename_notify=function(dt,old,name){me.rdocs.remove(dt,old);me.rdocs.add(dt,name,1);}
rename_observers.push(this);try{var rlist=JSON.parse(profile.recent);}
catch(e){return;}
var m=rlist.length;if(m>15)m=15;for(var i=0;i<m;i++){var rd=rlist[i]
if(rd[1]){var dt=rd[0];var dn=rd[1];this.rdocs.add(dt,dn,0);}}}
this.setup_help=function(){me.menu.add_top_menu('Tools',function(){},"sprite-tools");this.menu.add_item('Tools','Error Console',function(){err_console.show();});this.menu.add_item('Tools','Clear Cache',function(){$c('webnotes.session_cache.clear',{},function(r,rt){show_alert(r.message);})});if(has_common(user_roles,['Administrator','System Manager'])){this.menu.add_item('Tools','Download Backup',function(){me.download_backup();});}
this.menu.add_item('Tools','Web Notes Framework',function(){show_about();});}
this.setup_new=function(){me.menu.add_top_menu('New',function(){me.show_new();},'sprite-new');me.show_new=function(){if(!me.new_dialog){var d=new Dialog(240,140,"Create a new record");d.make_body([['HTML','Select'],['Button','Go',function(){me.new_dialog.hide();new_doc(me.new_sel.inp.value);}]]);d.onshow=function(){me.new_sel.inp.focus();}
me.new_dialog=d;var nl=profile.can_create.join(',').split(',');for(var i=0;i<nl.length;i++)nl[i]=get_doctype_label(nl[i]);me.new_sel=new SelectWidget(d.widgets['Select'],nl.sort(),'200px');me.new_sel.onchange=function(){me.new_dialog.hide();new_doc(me.new_sel.inp.value);}}
me.new_dialog.show();}}
this.setup_report_builder=function(){me.menu.add_top_menu('Report',function(){me.show_rb();},'sprite-report');me.show_rb=function(){if(!me.rb_dialog){var d=new Dialog(240,140,"Build a report for");d.make_body([['HTML','Select'],['Button','Go',function(){me.rb_dialog.hide();loadreport(me.rb_sel.inp.value,null,null,null,1);}]]);d.onshow=function(){me.rb_sel.inp.focus();}
me.rb_dialog=d;var nl=profile.can_get_report.join(',').split(',');for(var i=0;i<nl.length;i++)nl[i]=get_doctype_label(nl[i]);me.rb_sel=new SelectWidget(d.widgets['Select'],nl.sort(),'200px');me.rb_sel.onchange=function(){me.rb_dialog.hide();loadreport(me.rb_sel.inp.value,null,null,null,1);};}
me.rb_dialog.show();}}
this.setup_search=function(){me.menu.add_top_menu('Search',function(){me.search_dialog.show();},'sprite-search');var d=new Dialog(240,140,"Quick Search");d.make_body([['HTML','Select'],['Button','Go',function(){me.open_quick_search();}]]);d.onshow=function(){me.search_sel.inp.focus();}
me.search_dialog=d;keypress_observers.push({notify_keypress:function(ev,keycode){if(keycode==13&&me.search_dialog.display)me.open_quick_search();}});me.search_sel=new SelectWidget(d.widgets['Select'],[],'120px');me.search_sel.inp.value='Select...';me.open_quick_search=function(){me.search_dialog.hide();var v=sel_val(me.search_sel);if(v)selector.set_search(v);me.search_sel.disabled=1;selector.show();}
var nl=profile.can_read.join(',').split(',');for(var i=0;i<nl.length;i++)nl[i]=get_doctype_label(nl[i]);me.search_sel.set_options(nl.sort());me.search_sel.onchange=function(){me.open_quick_search();}
makeselector();}
this.setup_logout=function(){var w=$a($td(this.body_tab,0,2),'div','',{paddingTop:'2px',textAlign:'right'});this.right_table_style={fontSize:'11px',verticalAlign:'middle',height:'20px',paddingLeft:'4px',paddingRight:'4px'};var t=make_table(w,1,6,null,[],this.right_table_style);$y(t,{cssFloat:'right',color:'#FFF'});$td(t,0,0).innerHTML=user_fullname;$td(t,0,1).innerHTML='<span style="cursor: pointer;font-weight: bold" onclick="get_help()">Help</span>';$td(t,0,2).innerHTML='<span style="cursor: pointer;font-weight: bold" onclick="get_feedback()">Feedback</span>';$td(t,0,3).innerHTML='<span style="cursor: pointer;" onclick="loaddoc(\'Profile\', user)">Profile</span>';$td(t,0,4).innerHTML='<span style="cursor: pointer;" onclick="logout()">Logout</span>';this.menu_table_right=t;$y($td(t,0,5),{width:'18px'});this.spinner=$a($td(t,0,5),'img','',{display:'none'});this.spinner.src='images/ui/spinner.gif';}
this.download_backup=function(){$c('webnotes.utils.backups.get_backup',{},function(r,rt){});}
this.setup();}
var get_help=function(){msgprint('Help not implemented');}
var get_feedback=function(){var d=new Dialog(640,320,"Please give your feedback");d.make_body([['Text','Feedback'],['Button','Send',function(){$c_obj('Feedback Control','get_feedback',d.widgets['Feedback'].value,function(r,rt){d.hide();if(r.message)msgprint(r.message);})}]]);d.show();}
var nav_obj={}
nav_obj.observers=[];nav_obj.add_observer=function(o){nav_obj.observers.push(o);}
nav_obj.ol=[];nav_obj.open_notify=function(t,dt,dn,no_history){if(nav_obj.ol.length){var tmp=nav_obj.ol[nav_obj.ol.length-1];if(tmp&&tmp[0]==t&&tmp[1]==dt&&tmp[2]==dn)return;}
if(!no_history){var tmp=[];for(var i in nav_obj.ol)
if(!(nav_obj.ol[i][0]==t&&nav_obj.ol[i][1]==dt&&nav_obj.ol[i][2]==dn))tmp.push(nav_obj.ol[i]);nav_obj.ol=tmp;nav_obj.ol.push([t,dt,dn])
en_t=encodeURIComponent(t);en_dt=encodeURIComponent(dt);en_dn=dn?encodeURIComponent(dn):'';if(en_t=='Page'){var id=en_dt+(dn?('/'+en_dn):'')}else{var id=en_t+'/'+en_dt+(dn?('/'+en_dn):'')}
if(nav_obj.on_open)
nav_obj.on_open(id);dhtmlHistory.add('!'+id,'');}
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
function historyChange(newLocation,historyData){var t=nav_obj.get_page(newLocation)
for(var i=0;i<t.length;i++)
t[i]=decodeURIComponent(t[i]);if(nav_obj.ol.length){var c=nav_obj.ol[nav_obj.ol.length-1];if(t.length==2){if(c[0]==t[0]&&c[1]==t[1])return;}else{if(c[0]==t[0]&&c[1]==t[1]&&c[2]==t[2])return;}}
if(t[2])
var docname=history_get_name(t);if(t[0]=='Form'){_history_current=newLocation;if(docname.substr(0,3)=='New'){newdoc(t[1]);}else{loaddoc(t[1],docname);}}else if(t[0]=='Report'){_history_current=newLocation;loadreport(t[1],docname);}else if(t[0]=='Page'){_history_current=newLocation;loadpage(t[1]);}else if(t[0]=='Application'){_history_current=newLocation;loadapp(t[1]);}else if(t[0]=='DocBrowser'||t[0]=='List'){_history_current=newLocation;loaddocbrowser(t[1]);}};search_fields={};function setlinkvalue(name){selector.input.set_input(name);selector.hide();}
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
d.onhide=function(){if(page_body.wntoolbar)
page_body.wntoolbar.search_sel.disabled=0;if(d.input&&d.input.txt)
d.input.txt.onchange()}
btn.onclick=function(){if(this.disabled)return;this.set_working();d.set_doctype=d.sel_type;var q='';args={};if(d.input&&d.input.get_query){var doc={};args.is_simple=1;if(cur_frm)doc=locals[cur_frm.doctype][cur_frm.docname];var q=d.input.get_query(doc,d.input.doctype,d.input.docname);if(!q){return'';}}
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
var _loading_div;function set_loading(){if(page_body.wntoolbar)$ds(page_body.wntoolbar.spinner);$y(document.getElementsByTagName('body')[0],{cursor:'progress'});if(page_body.on_start_spinner)page_body.on_start_spinner();pending_req++;}
function hide_loading(){pending_req--;if(!pending_req){$y(document.getElementsByTagName('body')[0],{cursor:'default'});if(page_body.wntoolbar)
var d=page_body.wntoolbar.spinner;if(d)$dh(d);if(page_body.on_stop_spinner)page_body.on_stop_spinner();}}
var fcount=0;var frozen=0;var dialog_message;var dialog_back;function freeze(msg,do_freeze){if(msg){if(!dialog_message){dialog_message=$a('dialogs','div','dialog_message');}
var d=get_screen_dims();$y(dialog_message,{left:((d.w-250)/2)+'px',top:(get_scroll_top()+200)+'px'});dialog_message.innerHTML='<div style="font-size:16px; color: #444; font-weight: bold; text-align: center;">'+msg+'</div>';$ds(dialog_message);}
if(!dialog_back){dialog_back=$a($i('body_div'),'div','dialog_back');if(isIE)dialog_back.style['filter']='alpha(opacity=60)';}
$ds(dialog_back);$y(dialog_back,{height:get_page_size()[1]+'px'});fcount++;frozen=1;}
function unfreeze(){if(dialog_message)
$dh(dialog_message);if(!fcount)return;fcount--;if(!fcount){$dh(dialog_back);show_selects();frozen=0;}}
function hide_selects(){}
function show_selects(){}
var err_console;var err_list=[];function errprint(t){err_list[err_list.length]=('<pre style="font-family: Courier, Fixed; font-size: 11px; border-bottom: 1px solid #AAA; overflow: auto; width: 90%;">'+t+'</pre>');}
function submit_error(e){if(isIE){var t='Explorer: '+e+'\n'+e.description;}else{var t='Mozilla: '+e.toString()+'\n'+e.message+'\nLine Number:'+e.lineNumber;}
errprint(e+'\nLine Number:'+e.lineNumber+'\nStack:'+e.stack);}
function setup_err_console(){err_console=new Dialog(640,480,'Error Console')
err_console.make_body([['HTML','Error List'],['Button','Clear'],['HTML','Error Report']]);var span=$a(err_console.widgets['Error Report'],'span','link_type');span.innerHTML='Send Error Report';span.onclick=function(){msg=prompt('How / where did you get the error [optional]')
var call_back=function(r,rt){err_console.hide();msgprint("Error Report Sent")}
$c('webnotes.utils.send_error_report',{'err_msg':err_console.rows['Error List'].innerHTML,'msg':msg},call_back);}
err_console.widgets['Clear'].onclick=function(){err_list=[];err_console.rows['Error List'].innerHTML='';err_console.hide();}
err_console.onshow=function(){err_console.rows['Error List'].innerHTML='<div style="padding: 16px; height: 360px; width: 90%; overflow: auto;">'
+err_list.join('<div style="height: 10px; margin-bottom: 10px; border-bottom: 1px solid #AAA"></div>')+'</div>';}}
startup_list.push(setup_err_console);var about_dialog;function show_about(){if(!about_dialog){var d=new Dialog(360,480,'About')
d.make_body([['HTML','info']]);d.rows['info'].innerHTML="<div style='padding: 16px;'><center>"
+"<h2>Powered by Web Notes Framework</h2>"
+"<p style='color: #888'>Open Source Python + JS Framework</p>"
+"<p>Code Repository: <a href='http://code.google.com/p/wnframework'>http://code.google.com/p/wnframework</a></p>"
+"<p>Forum: <a href='http://groups.google.com/group/wnframework'>http://groups.google.com/group/wnframework</a></p>"
+"<p>Website: <a href='http://wnframework.org'>http://wnframework.org/</a></p>"
+"</div>";about_dialog=d;}
about_dialog.show();}
function loadreport(dt,rep_name,onload,menuitem,reset_report){dt=get_label_doctype(dt);var show_report_builder=function(rb_con){if(!_r.rb_con){_r.rb_con=rb_con;}
_r.rb_con.set_dt(dt,function(rb){if(rep_name){var t=rb.current_loaded;rb.load_criteria(rep_name);if(onload)
onload(rb);if((rb.dt)&&(!rb.dt.has_data()||rb.current_loaded!=t))
rb.dt.run();}else{if(reset_report){rb.reset_report();}}
if(!rb.forbidden){page_body.change_to('Report Builder');nav_obj.open_notify('Report',dt,rep_name);}});}
new_widget('_r.ReportContainer',show_report_builder,1);}
var load_doc=loaddoc;function loaddoc(doctype,name,onload,menuitem,from_archive){doctype=get_label_doctype(doctype);if(frms['DocType']&&frms['DocType'].opendocs[doctype]){msgprint("Cannot open an instance of \""+doctype+"\" when the DocType is open.");return;}
if(doctype=='DocType'&&frms[name]){msgprint("Cannot open DocType \""+name+"\" when its instance is open.");return;}
var show_form=function(f){if(!_f.frm_con&&f){_f.frm_con=f;}
if(!frms[doctype]){_f.add_frm(doctype,show_doc,name,from_archive);}else if(LocalDB.is_doc_loaded(doctype,name)){show_doc();}else{$c('webnotes.widgets.form.getdoc',{'name':name,'doctype':doctype,'user':user,'from_archive':(from_archive?1:0)},show_doc,null,null);}}
var show_doc=function(r,rt){if(locals[doctype]&&locals[doctype][name]){page_body.set_status('Done');var frm=frms[doctype];frm.refresh(name);if(!frm.in_dialog)
nav_obj.open_notify('Form',doctype,name);if(onload)onload();}else{if(r.exc){msgprint('There were errors while loading '+doctype+' '+name);}
loadpage('_home');}}
new_widget('_f.FrmContainer',show_form,1);}
function new_doc(doctype,onload,in_dialog,on_save_callback,cdt,cdn,cnic){doctype=get_label_doctype(doctype);if(!doctype){if(cur_frm)doctype=cur_frm.doctype;else return;}
var show_doc=function(){frm=frms[doctype];if(frm.perm[0][CREATE]==1){if(frm.meta.issingle){var dn=doctype;LocalDB.set_default_values(locals[doctype][doctype]);}else
var dn=LocalDB.create(doctype);if(onload)onload(dn);if(frm.in_dialog){var fd=_f.frm_dialog;fd.cdt=cdt;fd.cdn=cdn;fd.cnic=cnic;fd.on_save_callback=on_save_callback;}else{nav_obj.open_notify('Form',doctype,dn);}
frm.refresh(dn);}else{msgprint('error:Not Allowed To Create '+doctype+'\nContact your Admin for help');}}
var show_form=function(){if(!_f.frm_con){_f.frm_con=new _f.FrmContainer();}
if(!frms[doctype])
_f.add_frm(doctype,show_doc);else
show_doc(frms[doctype]);}
new_widget('_f.FrmContainer',show_form,1);}
var newdoc=new_doc;var pscript={};var cur_page;function loadpage(page_name,call_back,no_history){if(page_name=='_home')
page_name=home_page;var fn=function(r,rt){page_body.set_status('Done');if(page_body.pages[page_name]){var p=page_body.pages[page_name]
page_body.change_to(page_name);}else{var p=render_page(page_name);if(!p)return;}
cur_page=page_name;if(call_back)call_back();scroll(0,0);pscript.update_page_history(page_name,no_history)
try{if(pscript['refresh_'+page_name])pscript['refresh_'+page_name]();}catch(e){submit_error(e);}}
if(get_local('Page',page_name)||page_body.pages[page_name])
fn();else{args=get_url_dict();args.name=page_name;$c('webnotes.widgets.page.getpage',args,fn);}}
pscript.update_page_history=function(page_name,no_history){var arg=null;if(window.location.hash){var t=nav_obj.get_page(window.location.hash)}else if(get_url_arg('page')){var t=nav_obj.get_page(get_url_arg('page'))}else{return;}
if(t[1]==page_name)arg=t[2];nav_obj.open_notify('Page',page_name,arg,no_history);}
function loadscript(src,call_back){set_loading();var script=$a('head','script');script.type='text/javascript';script.src=src;script.onload=function(){if(call_back)call_back();hide_loading();}
script.onreadystatechange=function(){if(this.readyState=='complete'||this.readyState=='loaded'){hide_loading();call_back();}}}
var doc_browser_page;function loaddocbrowser(dt,label,fields){dt=get_label_doctype(dt);if(!doc_browser_page)
doc_browser_page=new ItemBrowserPage();doc_browser_page.show(dt,label,fields);nav_obj.open_notify('List',dt,'');}
var uploaders={};var upload_frame_count=0;Uploader=function(parent,args,callback){var id='frame'+upload_frame_count;upload_frame_count++;this.callback=callback;var div=$a(parent,'div');div.innerHTML='<iframe id="'+id+'" name="'+id+'" src="blank1.html" style="width:0px; height:0px; border:0px"></iframe>';var div=$a(parent,'div');div.innerHTML='<form method="POST" enctype="multipart/form-data" action="'+outUrl+'" target="'+id+'"></form>';var ul_form=div.childNodes[0];var f_list=[];var inp_fdata=$a_input($a(ul_form,'span'),'file',{name:'filedata'},{marginLeft:'7px'});var inp=$a_input($a(ul_form,'span'),'hidden',{name:'cmd'});inp.value='uploadfile';var inp=$a_input($a(ul_form,'span'),'hidden',{name:'uploader_id'});inp.value=id;var inp=$a_input($a(ul_form,'span'),'submit',null,{marginLeft:'7px'});inp.value='Upload';$y(inp,{width:'80px'});$wid_normal(inp);inp.onmouseover=function(){$wid_active(this);}
inp.onmouseout=function(){$wid_normal(this);}
inp.onmousedown=function(){$wid_pressed(this);}
inp.onmouseup=function(){$wid_active(inp);}
for(var key in args){var inp=$a_input($a(ul_form,'span'),'hidden',{name:key});inp.value=args[key];}
uploaders[id]=this;}
function upload_callback(id,fid){uploaders[id].callback(fid);}
var pages=[];var stylesheets=[];function Page(page_name,content){var me=this;this.name=page_name;this.onshow=function(){set_title(me.doc.page_title?me.doc.page_title:me.name);try{if(pscript['onshow_'+me.name])pscript['onshow_'+me.name]();}catch(e){submit_error(e);}
cur_frm=null;}
this.wrapper=page_body.add_page(page_name,this.onshow);this.cont=this.wrapper
if(content)
this.wrapper.innerHTML=content;if(page_name==home_page)
pages['_home']=this;return this;}
function render_page(page_name,menuitem){if(!page_name)return;if((!locals['Page'])||(!locals['Page'][page_name])){loadpage('_home');return;}
var pdoc=locals['Page'][page_name];if(pdoc.style)set_style(pdoc.style)
if(pdoc.stylesheet){set_style(locals.Stylesheet[pdoc.stylesheet].stylesheet);stylesheets.push(pdoc.stylesheet);}
var p=new Page(page_name,pdoc._Page__content?pdoc._Page__content:pdoc.content);var script=pdoc.__script?pdoc.__script:pdoc.script;p.doc=pdoc;if(script){try{eval(script);}catch(e){submit_error(e);}}
page_body.change_to(page_name);try{if(pscript['onload_'+page_name])pscript['onload_'+page_name]();}catch(e){submit_error(e);}
return p;}
function refresh_page(page_name){var fn=function(r,rt){render_page(page_name)}
$c('webnotes.widgets.page.getpage',{'name':page_name,stylesheets:JSON.stringify(stylesheets)},fn);}
ItemBrowserPage=function(){this.lists={};this.dt_details={};this.cur_list=null;this.my_page=page_body.add_page('ItemBrowser');this.wrapper=$a(this.my_page,'div');}
ItemBrowserPage.prototype.show=function(dt,label,field_list){var me=this;if(this.cur_list&&this.cur_list.dt!=dt)$dh(this.cur_list.layout.wrapper);if(!me.lists[dt]){me.lists[dt]=new ItemBrowser(me.wrapper,dt,label,field_list);}
me.cur_list=me.lists[dt];me.cur_list.show();page_body.change_to('ItemBrowser');}
ItemBrowser=function(parent,dt,label,field_list){var me=this;this.label=label?label:dt;this.dt=dt;this.field_list=field_list;this.tag_filter_dict={};this.items=[];this.cscript={};var l=get_doctype_label(dt);l=(l.toLowerCase().substr(-4)=='list')?l:(l+' List')
this.layout=new wn.PageLayout({parent:parent,main_width:'75%',sidebar_width:'25%',heading:l})
this.layout.no_records=$a($td(this.layout.wtab,0,0),'div');this.desc_area=$a(this.layout.head,'div','field_description','');$dh(this.layout.page_head.separator);this.no_result_area=$a(this.layout.no_records,'div','layout_wrapper',{fontSize:'14px',textAlign:'center',padding:'200px 0px'});this.layout.loading=$a($td(this.layout.wtab,0,0),'div','layout_wrapper',{padding:'200px 0px',textAlign:'center',fontSize:'14px',color:'#444',display:'none'});this.layout.loading.innerHTML='Loading<img src="images/ui/button-load.gif" style="margin-bottom: -2px; margin-left: 8px">';this.setup_toolbar();this.setup_sidebar();}
ItemBrowser.prototype.show_area=function(area){$ds(this.layout[area]);var al=['loading','no_records','main'];for(var a in al){if(al[a]!=area)
$dh(this.layout[al[a]]);}}
ItemBrowser.prototype.setup_sidebar=function(){var me=this;$y(this.layout.sidebar_area,{paddingTop:'53px'});this.sidebar=new wn.widgets.PageSidebar(this.layout.sidebar_area,{sections:[{title:'Top Tags',render:function(body){new wn.widgets.TagCloud(body,me.dt,function(tag){me.set_tag_filter(tag)});}}]});}
ItemBrowser.prototype.setup_toolbar=function(){var me=this;var parent=this.layout.toolbar_area
this.main_toolbar=$a(parent,'div','',{padding:'3px',backgroundColor:'#EEE'});$br(this.main_toolbar,'3px');$gr(this.main_toolbar,'#DDD','#CCC');this.sub_toolbar=$a(parent,'div','',{marginBottom:'7px',padding:'3px',textAlign:'right',fontSize:'11px',color:'#444'});this.archives_label=$a(parent,'div','help_box_big',{display:'none'},'Showing from Archives');var span=$a(this.archives_label,'span','link_type',{marginLeft:'8px'},'Show Active');span.onclick=function(){me.show_archives.checked=0;me.show_archives.onclick();}
this.trend_area=$a(parent,'div','',{marginBottom:'16px',padding:'4px',backgroundColor:'#EEF',border:'1px solid #CCF',display:'none'});$br(this.trend_area,'5px');this.tag_filters=$a(parent,'div','',{marginBottom:'8px',display:'none',padding:'6px 8px 8px 8px',backgroundColor:'#FFD'});var span=$a(this.tag_filters,'span','',{marginRight:'4px',color:'#444'});span.innerHTML='<i>Showing for:</i>';this.tag_area=$a(this.tag_filters,'span');var div=$a(parent,'div','',{margin:'3px 5px'});var chk=$a_input(div,'checkbox');var lab=$a(div,'span','',{marginLeft:'9px'},'Select All');chk.onclick=function(){for(var i=0;i<me.items.length;i++){me.items[i].check.checked=this.checked;me.items[i].check.onclick();}}
this.select_all=chk;}
ItemBrowser.prototype.make_checkbox=function(status,checked){var me=this;var chk=$a_input(this.sub_toolbar,'checkbox');var lab=$a(this.sub_toolbar,'span','',{marginRight:'8px'},'Show '+status);chk.onclick=function(){me.run();}
chk.checked=checked;this['check_'+status]=chk;}
ItemBrowser.prototype.get_status_check=function(){ret=[];if(this.check_Draft.checked)ret.push(0);if(this.check_Submitted.checked)ret.push(1);if(this.check_Cancelled.checked)ret.push(2);if(!ret.length){msgprint('Atleast of Draft, Submitted or Cancelled must be checked!');return}
return ret;}
ItemBrowser.prototype.make_toolbar=function(){var me=this;if(this.dt_details.description)this.desc_area.innerHTML=this.dt_details.description;if(inList(profile.can_create,this.dt)){this.new_button=$btn(this.main_toolbar,'+ New '+get_doctype_label(this.dt),function(){newdoc(me.dt)},{fontWeight:'bold',marginRight:'0px'},'green');}
if(in_list(profile.can_write,this.dt)){this.archive_btn=$btn(this.main_toolbar,'Archive',function(){me.archive_items();},{marginLeft:'24px'});}
if(this.dt_details.can_cancel){this.delete_btn=$btn(this.main_toolbar,'Delete',function(){me.delete_items();});}
if(this.archive_btn&&this.delete_btn)
$btn_join(this.archive_btn,this.delete_btn)
this.search_input=$a(this.main_toolbar,'input','',{width:'120px',marginLeft:'24px',border:'1px solid #AAA'});this.search_btn=$btn(this.main_toolbar,'Search',function(){me.run();},{marginLeft:'4px'});this.filters_on=0;this.filter_btn=$ln(this.main_toolbar,'Show Filters',function(){me.show_filters();},{marginLeft:'24px'});if(this.dt_details.submittable){this.make_checkbox('Draft',1)
this.make_checkbox('Submitted',1)
this.make_checkbox('Cancelled',0)}
this.set_archiving();}
ItemBrowser.prototype.set_archiving=function(){var me=this;this.show_archives=$a_input(this.sub_toolbar,'checkbox');var lab=$a(this.sub_toolbar,'span');lab.innerHTML='Show Archives';this.show_archives.onclick=function(){if(this.checked){if(me.archive_btn)me.archive_btn.innerHTML='Restore';$(me.archives_label).slideDown();}else{if(me.archive_btn)me.archive_btn.innerHTML='Archive';$(me.archives_label).slideUp();}
me.run();}}
ItemBrowser.prototype.show_filters=function(){if(this.filters_on){$(this.lst.filter_wrapper).slideUp();this.filters_on=0;this.filter_btn.innerHTML='Advanced Search';}else{$(this.lst.filter_wrapper).slideDown();this.filters_on=1;this.filter_btn.innerHTML='Hide Filters';}}
ItemBrowser.prototype.show_activity=function(){var me=this;if(this.trend_on){$(this.trend_area).slideUp();me.trend_btn.innerHTML='Show Activity';me.trend_on=0;}else{if(!this.trend_loaded){var callback=function(r,rt){me.show_trend(r.message.trend);$(me.trend_area).slideDown();me.trend_btn.done_working();me.trend_btn.innerHTML='Hide Activity';me.trend_loaded=1;me.trend_on=1;}
$c('webnotes.widgets.menus.get_trend',{'dt':this.dt},callback);me.trend_btn.set_working();}else{$(this.trend_area).slideDown();me.trend_btn.innerHTML='Hide Activity';me.trend_on=1;}}}
ItemBrowser.prototype.show=function(onload){$ds(this.layout.wrapper);if(onload)this.cscript.onload=onload
if(this.loaded&&this.lst.n_records)return;this.show_area('loading');var me=this;var callback=function(r,rt){if(r.message=='Yes'){if(!me.loaded){me.load_details();}else{me.show_results();}}else{if(me.cscript.onload)me.cscript.onload(this);me.show_no_result();}}
$c('webnotes.widgets.menus.has_result',{'dt':this.dt},callback);}
ItemBrowser.prototype.load_details=function(){var me=this;var callback=function(r,rt){me.dt_details=r.message;if(r.message){me.make_toolbar();me.make_the_list(me.dt,me.layout.body);if(me.cscript.onload)
me.cscript.onload(me);me.show_results();}}
var fl=this.field_list?this.field_list.split('\n'):[];$c('webnotes.widgets.menus.get_dt_details',{'dt':this.dt,'fl':JSON.stringify(fl)},callback);this.loaded=1;}
ItemBrowser.prototype.show_results=function(){this.show_area('main');set_title(get_doctype_label(this.label));}
ItemBrowser.prototype.show_trend=function(trend){var maxval=0;for(var key in trend){if(trend[key]>maxval)maxval=trend[key]};var div=$a(this.trend_area,'div','',{marginLeft:'32px'});div.innerHTML='Activity in last 30 days';var wrapper_tab=make_table(this.trend_area,1,2,'100%',['20px',null],{padding:'2px 4px',fontSize:'10px',color:'#888'});var ylab_tab=make_table($td(wrapper_tab,0,0),2,1,'100%',['100%'],{verticalAlign:'top',textAlign:'right',height:'24px'});$td(ylab_tab,0,0).innerHTML=maxval;$y($td(ylab_tab,1,0),{verticalAlign:'bottom'});$td(ylab_tab,1,0).innerHTML='0';var tab=make_table($td(wrapper_tab,0,1),1,30,'100%',[],{width:10/3+'%',border:'1px solid #DDD',height:'40px',verticalAlign:'bottom',textAlign:'center',padding:'2px',backgroundColor:'#FFF'});var labtab=make_table($td(wrapper_tab,0,1),1,6,'100%',[],{width:100/6+'%',border:'1px solid #EEF',height:'16px',color:'#888',textAlign:'right',fontSize:'10px'});for(var i=0;i<30;i++){var div=$a($td(tab,0,29-i),'div','',{backgroundColor:'#4AC',width:'50%',margin:'auto',height:(trend[i+'']?(trend[i+'']*100/maxval):0)+'%'});div.setAttribute('title',trend[i]+' records');if(i%5==0){$td(labtab,0,5-(i/5)).innerHTML=dateutil.obj_to_user(dateutil.add_days(new Date(),-i));$y($td(tab,0,i-1),{'backgroundColor':'#EEE'});}}
$td(labtab,0,5).innerHTML='Today';}
ItemBrowser.prototype.show_no_result=function(){this.show_area('no_records');this.no_result_area.innerHTML=repl('No %(dt)s found. <span class="link_type" onclick="newdoc(\'%(dt)s\')">Click here</span> to create your first %(dt)s!',{dt:get_doctype_label(this.dt)});set_title(get_doctype_label(this.label));}
ItemBrowser.prototype.make_new=function(dt,label,field_list){this.make_the_list(dt,this.layout.body);}
ItemBrowser.prototype.add_search_conditions=function(q){if(this.search_input.value){q.conds+=' AND '+q.table+'.name LIKE "%'+this.search_input.value+'%"';}}
ItemBrowser.prototype.add_tag_conditions=function(q){var me=this;if(keys(me.tag_filter_dict).length){var cl=[];for(var key in me.tag_filter_dict){var val=key;var op='=';var fn=me.tag_filter_dict[key].fieldname;fn=fn?fn:'_user_tags';if(fn=='docstatus')val=(key=='Draft'?'0':'1');else if(fn=='_user_tags'){val='%,'+key+'%';op=' LIKE ';}
cl.push(q.table+'.`'+fn+'`'+op+'"'+val+'"');}
if(cl)
q.conds+=' AND '+cl.join(' AND ')+' ';}}
ItemBrowser.prototype.make_the_list=function(dt,wrapper){var me=this;var lst=new Listing(dt,1);lst.dt=dt;lst.cl=this.dt_details.columns;lst.opts={cell_style:{padding:'0px 2px'},alt_cell_style:{backgroundColor:'#FFFFFF'},hide_export:1,hide_print:1,hide_rec_label:0,show_calc:0,show_empty_tab:0,show_no_records_label:1,show_new:0,show_report:1,no_border:1,append_records:1,formatted:1}
if(user_defaults.hide_report_builder)lst.opts.show_report=0;lst.is_std_query=1;lst.get_query=function(){q={};var fl=[];q.table=repl('`%(prefix)s%(dt)s`',{prefix:(me.show_archives.checked?'arc':'tab'),dt:this.dt});for(var i=0;i<this.cl.length;i++){if(!(me.show_archives&&me.show_archives.checked&&this.cl[i][0]=='_user_tags'))
fl.push(q.table+'.`'+this.cl[i][0]+'`')}
if(me.dt_details.submittable){fl.push(q.table+'.docstatus');var tmp=me.get_status_check();if(!tmp){this.query=null;return;}
q.conds=q.table+'.docstatus in ('+tmp.join(',')+') ';}else{q.conds=q.table+'.docstatus != 2'}
q.fields=fl.join(', ');me.add_tag_conditions(q);me.add_search_conditions(q);this.query=repl("SELECT %(fields)s FROM %(table)s WHERE %(conds)s",q);this.query_max=repl("SELECT COUNT(*) FROM %(table)s WHERE %(conds)s",q);if(me.show_archives.checked)
this.prefix='arc';else
this.prefix='tab'}
lst.colwidths=['100%'];lst.coltypes=['Data'];lst.coloptions=[''];lst.show_cell=function(cell,ri,ci,d){me.items.push(new ItemBrowserItem(cell,d[ri],me));}
lst.make(wrapper);var sf=me.dt_details.filters;for(var i=0;i<sf.length;i++){var fname=sf[i][0];var label=sf[i][1];var ftype=sf[i][2];var fopts=sf[i][3];if(in_list(['Int','Currency','Float','Date'],ftype)){lst.add_filter('From '+label,ftype,fopts,dt,fname,'>=');lst.add_filter('To '+label,ftype,fopts,dt,fname,'<=');}else{lst.add_filter(label,ftype,fopts,dt,fname,(in_list(['Data','Text','Link'],ftype)?'LIKE':''));}}
$dh(lst.filter_wrapper);lst.set_default_sort('modified','DESC');this.lst=lst;lst.run();}
ItemBrowser.prototype.run=function(){this.items=[];this.select_all.checked=false;this.lst.run();}
ItemBrowser.prototype.get_checked=function(){var il=[];for(var i=0;i<this.items.length;i++){if(this.items[i].check.checked)il.push([this.dt,this.items[i].dn]);}
return il;}
ItemBrowser.prototype.delete_items=function(){var me=this;if(confirm('This is PERMANENT action and you cannot undo. Continue?'))
$c('webnotes.widgets.menus.delete_items',{'items':JSON.stringify(this.get_checked())},function(r,rt){if(!r.exc)me.run();})}
ItemBrowser.prototype.archive_items=function(){var me=this;var arg={'action':this.show_archives.checked?'Restore':'Archive','items':JSON.stringify(this.get_checked())}
$c('webnotes.widgets.menus.archive_items',arg,function(r,rt){if(!r.exc)me.run();})}
ItemBrowser.prototype.set_tag_filter=function(tag){var me=this;if(in_list(keys(me.tag_filter_dict),tag.label))return;var filter_tag=new SingleTag({parent:me.tag_area,label:tag.label,dt:me.dt,color:tag.color});filter_tag.fieldname=tag.fieldname;filter_tag.remove=function(tag_remove){$(tag_remove.body).fadeOut();delete me.tag_filter_dict[tag_remove.label];if(!keys(me.tag_filter_dict).length){$(me.tag_filters).slideUp();}
me.run();}
me.tag_filter_dict[tag.label]=filter_tag;$ds(me.tag_filters);me.run();}
function ItemBrowserItem(parent,det,ib){this.wrapper=$a(parent,'div');$y(this.wrapper,{borderTop:'1px solid #DDD'});this.tab=make_table(this.wrapper,1,2,'100%',['24px',null]);this.body=$a($td(this.tab,0,1),'div');this.link_area=$a(this.body,'div')
this.details_area=this.link_area
this.det=det;this.ib=ib;this.dn=det[0];this.make_check();this.make_tags();this.make_details();this.add_timestamp();}
ItemBrowserItem.prototype.make_check=function(){if(this.ib.archive_btn||this.ib.delete_btn){var me=this;this.check=$a_input($td(this.tab,0,0),'checkbox');this.check.onclick=function(){if(this.checked){$y(me.wrapper,{backgroundColor:'#FFC'});}else{$y(me.wrapper,{backgroundColor:'#FFF'});}}}}
ItemBrowserItem.prototype.make_details=function(){var me=this;var div=this.details_area;var span=$a(this.link_area,'span','link_type',{fontWeight:'bold',marginRight:'7px'});span.innerHTML=me.dn;span.onclick=function(){loaddoc(me.ib.dt,me.dn,null,null,(me.ib.show_archives?me.ib.show_archives.checked:null));}
var cl=me.ib.dt_details.columns;var tag_fields=me.ib.dt_details.tag_fields?me.ib.dt_details.tag_fields.split(','):[];for(var i=0;i<tag_fields.length;i++)tag_fields[i]=strip(tag_fields[i]);if(me.ib.dt_details.subject){var det_dict={};for(var i=0;i<cl.length;i++){var fieldname=cl[i][0];det_dict[fieldname]=me.det[i]?me.det[i]:'';if(in_list(tag_fields,fieldname))
me.taglist.add_tag(me.det[i],1,fieldname);}
var s=repl(me.ib.dt_details.subject,det_dict);if(s.substr(0,5)=='eval:')s=eval(s.substr(5));$a(div,'span','',{color:'#444'},s)}else{var tmp=[];var first_property=1;for(var i=3;i<me.det.length;i++){if(cl[i]&&cl[i][1]&&me.det[i]){if(cl[i][1].indexOf('Status')!=-1||cl[i][1].indexOf('Group')!=-1||cl[i][1].indexOf('Priority')!=-1||cl[i][1].indexOf('Type')!=-1){me.taglist.add_tag(me.det[i],1,cl[i][0],'#c0c0c0');}else{if(!first_property){var span=$a(div,'span');span.innerHTML=',';}else first_property=0;var span=$a(div,'span','',{color:'#888'});span.innerHTML=' '+cl[i][1]+': ';var span=$a(div,'span');$s(span,me.det[i],(cl[i][2]=='Link'?'Data':cl[i][2]),cl[i][3]);}}}}}
ItemBrowserItem.prototype.make_tags=function(){var docstatus=cint(this.det[this.det.length-1]);var me=this;var tl=this.det[2]?this.det[2].split(','):[];var div=$a(this.body,'div','',{margin:'7px 0px'})
this.taglist=new TagList(div,tl,this.ib.dt,this.dn,0,function(tag){me.ib.set_tag_filter(tag);});}
ItemBrowserItem.prototype.add_timestamp=function(){var div=$a(this.body,'div','',{color:'#888',fontSize:'11px'});div.innerHTML=comment_when(this.det[1]);}
wn.PageLayout=function(args){$.extend(this,args)
this.wrapper=$a(this.parent,'div');this.wtab=make_table(this.wrapper,1,2,'100%',[this.main_width,this.sidebar_width]);this.main=$a($td(this.wtab,0,0),'div','layout_wrapper');this.sidebar_area=$a($td(this.wtab,0,1),'div');this.head=$a(this.main,'div');this.toolbar_area=$a(this.main,'div');this.body=$a(this.main,'div');this.footer=$a(this.main,'div');if(this.heading){this.page_head=new PageHeader(this.head,this.heading);}}
wn.widgets.PageSidebar=function(parent,opts){this.opts=opts
this.sections={}
this.wrapper=$a(parent,'div','psidebar-wrapper')
this.refresh=function(){this.wrapper.innerHTML=''
if(this.opts.title)
this.make_head();for(var i=0;i<this.opts.sections.length;i++){var section=this.opts.sections[i];if((section.display&&section.display())||!section.display){this.sections[section.title]=new wn.widgets.PageSidebarSection(this,section);}}
if(this.opts.onrefresh){this.opts.onrefresh(this)}}
this.make_head=function(){this.head=$a(this.wrapper,'div','psidebar-head','',this.opts.title);}
this.refresh();}
wn.widgets.PageSidebarSection=function(sidebar,opts){this.items=[];this.sidebar=sidebar;this.wrapper=$a(sidebar.wrapper,'div','psidebar-section');this.head=$a(this.wrapper,'div','psidebar-section-head','',opts.title);this.body=$a(this.wrapper,'div','psidebar-section-body');$br(this.wrapper,'3px');this.opts=opts;this.make_items=function(){for(var i=0;i<this.opts.items.length;i++){var item=this.opts.items[i];if((item.display&&item.display())||!item.display){var div=$a(this.body,'div','psidebar-section-item');this.make_one_item(item,div);}}}
this.make_one_item=function(item,div){if(item.type.toLowerCase()=='link')
this.items[item.label]=new wn.widgets.PageSidebarLink(this,item,div);else if(item.type.toLowerCase()=='button')
this.items[item.label]=new wn.widgets.PageSidebarButton(this,this.opts.items[i],div);else if(item.type.toLowerCase()=='html')
this.items[item.label]=new wn.widgets.PageSidebarHTML(this,this.opts.items[i],div);}
this.add_icon=function(parent,icon){if(icon.substr(0,3)=='ic-'){var img=$a(parent,'div','wn-icon '+icon,{cssFloat:'left',marginRight:'7px',marginBottom:'-3px'});}else{var img=$a(parent,'img','',{marginRight:'7px',marginBottom:'-3px'});img.src='images/icons/'+icon;}}
this.refresh=function(){this.body.innerHTML='';if(this.opts.render){this.opts.render(this.body);}
else
this.make_items();}
this.refresh();}
wn.widgets.PageSidebarLink=function(section,opts,wrapper){this.wrapper=wrapper;this.section=section;this.opts=opts;var me=this;if(opts.icon){section.add_icon(this.wrapper,opts.icon);}
this.ln=$a(this.wrapper,'span','link_type psidebar-section-link',opts.style,opts.label);this.ln.onclick=function(){me.opts.onclick(me)};}
wn.widgets.PageSidebarButton=function(section,opts,wrapper){this.wrapper=wrapper;this.section=section;this.opts=opts;var me=this;this.btn=$btn(this.wrapper,opts.label,opts.onclick,opts.style,opts.color);}
wn.widgets.PageSidebarHTML=function(section,opts,wrapper){wrapper.innerHTML=opts.content}
wn.widgets.Footer=function(args){$.extend(this,args);this.make=function(){this.wrapper=$a(this.parent,'div','std-footer');this.table=make_table(this.wrapper,1,this.columns,[],{width:100/this.columns+'%'});this.render_items();}
this.render_items=function(){for(var i=0;i<this.items.length;i++){var item=this.items[i];var div=$a($td(this.table,0,item.column),'div','std-footer-item');div.label=$a($a(div,'div'),'span','link_type','',item.label);div.label.onclick=item.onclick;if(item.description){div.description=$a(div,'div','field_description','',item.description);}}}
if(this.items)
this.make();}
var locals={};var fields={};var fields_list={};var LocalDB={};var READ=0;var WRITE=1;var CREATE=2;var SUBMIT=3;var CANCEL=4;var AMEND=5;LocalDB.getchildren=function(child_dt,parent,parentfield,parenttype){var l=[];for(var key in locals[child_dt]){var d=locals[child_dt][key];if((d.parent==parent)&&(d.parentfield==parentfield)){if(parenttype){if(d.parenttype==parenttype)l.push(d);}else{l.push(d);}}}
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
var getchildren=LocalDB.getchildren;var get_field=Meta.get_field;var createLocal=LocalDB.create;function compress_doclist(list){var kl={};var vl=[];var flx={};for(var i=0;i<list.length;i++){var o=list[i];var fl=[];if(!kl[o.doctype]){var tfl=['doctype','name','docstatus','owner','parent','parentfield','parenttype','idx','creation','modified','modified_by','__islocal','__deleted','__newname','__modified','_user_tags'];var fl=['doctype','name','docstatus','owner','parent','parentfield','parenttype','idx','creation','modified','modified_by','__islocal','__deleted','__newname','__modified','_user_tags'];for(key in fields[o.doctype]){if(!in_list(fl,key)&&!in_list(no_value_fields,fields[o.doctype][key].fieldtype)&&!fields[o.doctype][key].no_column){fl[fl.length]=key;tfl[tfl.length]=key}}
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
$c('webnotes.widgets.form.savedocs',{'docs':compress_doclist(doclist),'docname':dn,'action':save_action,'user':user},function(r,rtxt){if(f){f.savingflag=false;}
if(r.saved){if(onsave)onsave(r);}else{if(onerr)onerr(r);}},function(){if(f){f.savingflag=false;}},0,(f?'Saving...':''));}
if(doc.__islocal&&(doctype&&doctype.autoname&&doctype.autoname.toLowerCase()=='prompt')){var newname=prompt('Enter the name of the new '+dt,'');if(newname){doc.__newname=strip(newname);_save();}else{msgprint('Not Saved');onerr();}}else{_save();}}
function check_required(dt,dn,parent_dt){var doc=locals[dt][dn];if(doc.docstatus>1)return true;var fl=fields_list[dt];if(!fl)return true;var all_clear=true;var errfld=[];for(var i=0;i<fl.length;i++){var key=fl[i].fieldname;var v=doc[key];if(fl[i].reqd&&is_null(v)&&fl[i].fieldname){errfld[errfld.length]=fl[i].label;if(cur_frm){var f=cur_frm.fields_dict[fl[i].fieldname];if(f){if(f.set_as_error)f.set_as_error(1);if(!cur_frm.error_in_section&&f.parent_section){cur_frm.set_section(f.parent_section.sec_id);cur_frm.error_in_section=1;}}}
if(all_clear)all_clear=false;}}
if(errfld.length)msgprint('<b>Mandatory fields required in '+
(doc.parenttype?(fields[doc.parenttype][doc.parentfield].label+' (Table)'):get_doctype_label(doc.doctype))+':</b>\n'+errfld.join('\n'));return all_clear;}
function Body(){this.left_sidebar=null;this.right_sidebar=null;this.status_area=null;var me=this;page_body=this;this.no_of_columns=function(){var n=2;if(cint(me&&me.cp&&me.cp.right_sidebar_width))
n=n+1;return n;}
this.setup_page_areas=function(){var n=this.no_of_columns();this.body_table=make_table(this.body,1,n,'100%');$y(this.body_table,{tableLayout:'fixed'});var c=0;this.left_sidebar=$td(this.body_table,0,c);$y(this.left_sidebar,{width:cint(this.cp.left_sidebar_width)+'px'});c++;this.center=$a($td(this.body_table,0,c),'div');c++;if(cint(this.cp.right_sidebar_width)){this.right_sidebar=$td(this.body_table,0,c);$y(this.right_sidebar,{width:cint(this.cp.right_sidebar_width)+'px'})
c++;}
this.center.header=$a(this.center,'div');this.center.body=$a(this.center,'div');this.center.loading=$a(this.center,'div','',{margin:'200px 0px',fontSize:'14px',color:'#999',textAlign:'center'});this.center.loading.innerHTML='Loading...'}
this.setup_sidebar_menu=function(){if(this.left_sidebar&&this.cp.show_sidebar_menu){new_widget('SidebarMenu',function(m){sidebar_menu=m;m.make_menu('');});}}
this.setup_header_footer=function(){if(cint(this.cp.header_height)){var hh=this.cp.header_height?(cint(this.cp.header_height)+'px'):'0px';$y(this.header,{height:hh,borderBottom:'1px solid #CCC'});if(this.cp.client_name)this.banner_area.innerHTML=this.cp.client_name;}
var fh=this.cp.footer_height?(cint(this.cp.footer_height)+'px'):'0px';$y(this.footer,{height:fh});if(this.cp.footer_html)this.footer.innerHTML=this.cp.footer_html;}
this.run_startup_code=function(){if(this.cp.startup_css)
set_style(this.cp.startup_css);try{if(this.cp.startup_code)
eval(this.cp.startup_code);if(this.cp.custom_startup_code)
eval(this.cp.custom_startup_code);}catch(e){errprint(e);}}
this.setup=function(){this.cp=locals['Control Panel']['Control Panel'];this.wntoolbar_area=$a($i('body_div'),'div');this.wrapper=$a($i('body_div'),'div');this.banner_area=$a(this.wrapper,'div');;this.topmenu=$a(this.wrapper,'div');this.breadcrumbs=$a(this.wrapper,'div');this.body=$a(this.wrapper,'div');this.footer=$a(this.wrapper,'div');if(user_defaults.hide_sidebars){this.cp.left_sidebar_width=null;this.cp.right_sidebar_width=null;}
this.setup_page_areas();this.setup_header_footer();if(user=='Guest')user_defaults.hide_webnotes_toolbar=1;if(!cint(user_defaults.hide_webnotes_toolbar)||user=='Administrator'){this.wntoolbar=new WNToolbar(this.wntoolbar_area);$y(this.wrapper,{marginTop:this.wntoolbar.wrapper.offsetHeight+'px'});}
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
var popup_cont;var session={};var start_sid=null;function startup(){dhtmlHistory.initialize();dhtmlHistory.addListener(historyChange);start_sid=get_cookie('sid');popup_cont=$a(document.getElementsByTagName('body')[0],'div');var setup_globals=function(r){profile=r.profile;user=r.profile.name;user_fullname=profile.first_name+(r.profile.last_name?(' '+r.profile.last_name):'');user_defaults=profile.defaults;user_roles=profile.roles;user_email=profile.email;profile.start_items=r.start_items;home_page=r.home_page;_p.letter_heads=r.letter_heads;sys_defaults=r.sysdefaults;session.rt=profile.can_read;if(r.ipinfo)session.ipinfo=r.ipinfo;session.dt_labels=r.dt_labels;session.rev_dt_labels={}
_tags.color_map=r.tag_color_map;if(r.dt_labels){for(key in r.dt_labels)session.rev_dt_labels[r.dt_labels[key]]=key;}}
var setup_history=function(r){rename_observers.push(nav_obj);}
var setup_events=function(){addEvent('keyup',function(ev,target){for(var i in keypress_observers){if(keypress_observers[i])
keypress_observers[i].notify_keypress(ev,ev.keyCode);}});addEvent('click',function(ev,target){for(var i=0;i<click_observers.length;i++){if(click_observers[i])
click_observers[i].notify_click(ev,target);}});if(isIE){$op($i('dialog_back'),60);}}
var callback=function(r,rt){if(r.exc)msgprint(r.ext);setup_globals(r);setup_history();setup_events();var a=new Body();page_body.run_startup_code();page_body.setup_sidebar_menu();for(var i=0;i<startup_list.length;i++){startup_list[i]();}
$dh('startup_div');$ds('body_div');if(get_url_arg('embed')){newdoc(get_url_arg('embed'));return;}
var t=to_open();if(t){historyChange(t);}else if(home_page){loadpage(home_page);}}
if(keys(_startup_data).length&&_startup_data.docs){LocalDB.sync(_startup_data.docs);callback(_startup_data,'');if(_startup_data.server_messages)msgprint(_startup_data.server_messages);}else{if($i('startup_div'))
$c('startup',{},callback,null,1);}}
function to_open(){if(get_url_arg('page'))
return get_url_arg('page');var h=location.hash;if(h){return h.substr(1);}}
function logout(){$c('logout',args={},function(r,rt){if(r.exc){msgprint(r.exc);return;}
redirect_to_login();});}
function redirect_to_login(){if(login_file)
window.location.href=login_file;else
window.location.href='index.cgi';}
_p.def_print_style_body="html, body, div, span, td { font-family: Arial, Helvetica; font-size: 12px; }"
+"\npre { margin:0; padding:0;}"
_p.def_print_style_other="\n.simpletable, .noborder { border-collapse: collapse; margin-bottom: 10px;}"
+"\n.simpletable td {border: 1pt solid #000; vertical-align: top; padding: 2px; }"
+"\n.noborder td { vertical-align: top; }"
_p.go=function(html){var d=document.createElement('div')
d.innerHTML=html
$(d).printElement();}
_p.preview=function(html){var w=window.open('');w.document.write(html)
w.document.close();}
function setup_calendar(){var p=new Page('_calendar');p.wrapper.style.height='100%';p.wrapper.onshow=function(){if(!_c.calendar){new_widget('Calendar',function(c){_c.calendar=c;_c.calendar.init(p.cont);rename_observers.push(_c.calendar);});}}}
startup_list.push(setup_calendar);if(isIE6){var scroll_list=[]
window.onscroll=function(){for(var i=0;i<scroll_list.length;i++){scroll_list[i]();}}}
window.onload=function(){startup()}
var resize_observers=[]
function set_resize_observer(fn){if(resize_observers.indexOf(fn)==-1)resize_observers.push(fn);}
window.onresize=function(){return;var ht=get_window_height();for(var i=0;i<resize_observers.length;i++){resize_observers[i](ht);}}
get_window_height=function(){var ht=window.innerHeight?window.innerHeight:document.documentElement.offsetHeight?document.documentElement.offsetHeight:document.body.offsetHeight;var toolbarh=page_body.wntoolbar?page_body.wntoolbar.wrapper.offsetHeight:0
var bannerh=page_body.banner_area?page_body.banner_area.offsetHeight:0
var footerh=page_body.footer?page_body.footer.offsetHeight:0
ht=ht-bannerh-toolbarh-footerh;return ht;}
setup_shortcuts=function(){$(document).bind('keydown','ctrl+s',function(){if(cur_frm&&cur_frm.doc&&cur_frm.doc.docstatus==0)
cur_frm.save("Save")});$(document).bind('keydown','ctrl+n',function(){if(cur_frm)new_doc(cur_frm.doctype);else if(page_body.wntoolbar)page_body.wntoolbar.show_new();});$(document).bind('keydown','ctrl+p',function(){if(cur_frm)cur_frm.print_doc();});}
startup_list.push(setup_shortcuts);Calendar=function(){this.views=[];this.events={};this.has_event={};this.weekdays=new Array("Sun","Mon","Tue","Wed","Thu","Fri","Sat");}
Calendar.prototype.init=function(parent){this.wrapper=$a(parent,'div','cal_wrapper');this.page_head=new PageHeader(this.wrapper,'Calendar')
this.body=$a(this.wrapper,'div','cal_body');this.make_head_buttons();this.make_header();this.todays_date=new Date();this.selected_date=this.todays_date;this.selected_hour=8;this.views['Month']=new Calendar.MonthView(this);this.views['Week']=new Calendar.WeekView(this);this.views['Day']=new Calendar.DayView(this);this.cur_view=this.views['Day'];this.views['Day'].show();setTimeout(_c.set_height,100);set_resize_observer(_c.set_height);}
Calendar.prototype.rename_notify=function(dt,old_name,new_name){if(dt='Event'&&this.has_event[old_name])
this.has_event[old_name]=false;}
_c.set_height=function(){var cal_body_h=get_window_height()-_c.calendar.page_head.wrapper.offsetHeight-32;var cal_view_body_h=cal_body_h-_c.calendar.view_header.offsetHeight-32;var header_h=_c.calendar.cur_view.head_wrapper?_c.calendar.cur_view.head_wrapper.offsetHeight:0;var cal_view_main_h=cal_view_body_h-header_h;$y(_c.calendar.body,{height:cal_body_h+'px'})
$y(_c.calendar.cur_view.body,{height:cal_view_body_h+'px'})
$y(_c.calendar.cur_view.main,{height:cal_view_main_h+'px',overflow:'auto'})}
Calendar.prototype.make_header=function(){var me=this;this.view_header=$a(this.body,'div','cal_month_head',{paddingTop:'8px'});var tab=make_table(this.view_header,1,3,'50%',['100px',null,'100px'],{verticalAlign:'middle'});$y(tab,{margin:'auto'});var lbtn=$btn($td(tab,0,0),'&lt; Prev',function(){me.cur_view.prev()});var rbtn=$btn($td(tab,0,2),'Next &gt;',function(){me.cur_view.next()});$y($td(tab,0,1),{fontSize:'16px',textAlign:'center'})
this.view_title=$td(tab,0,1);}
Calendar.prototype.make_head_buttons=function(){var me=this;this.page_head.add_button('New Event',function(){me.add_event();},0,'ui-icon-plus',1);this.page_head.add_button('Month View',function(){me.refresh('Month');},0,'ui-icon-calculator');this.page_head.add_button('Weekly View',function(){me.refresh('Week');},0,'ui-icon-note');this.page_head.add_button('Daily View',function(){me.refresh('Day');},0,'ui-icon-calendar');}
Calendar.prototype.show_event=function(ev,cal_ev){var me=this;if(!this.event_dialog){var d=new Dialog(400,400,'Calendar Event');d.make_body([['HTML','Heading'],['Text','Description'],['Check','Public Event'],['Check','Cancel Event'],['HTML','Event Link'],['Button','Save']])
d.onshow=function(){var c=me.selected_date;var tmp=time_to_ampm(this.ev.event_hour);tmp=tmp[0]+':'+tmp[1]+' '+tmp[2];this.widgets['Heading'].innerHTML='<div style="text-align: center; padding:4px; font-size: 14px">'
+_c.calendar.weekdays[c.getDay()]+', '+c.getDate()+' '+month_list_full[c.getMonth()]+' '+c.getFullYear()
+' - <b>'+tmp+'</b></div>';this.widgets['Description'].value=cstr(this.ev.description);this.widgets['Public Event'].checked=false;this.widgets['Cancel Event'].checked=false;if(this.ev.event_type=='Public')
this.widgets['Public Event'].checked=true;this.widgets['Event Link'].innerHTML='';var div=$a(this.widgets['Event Link'],'div','link_type',{margin:'4px 0px'});div.onclick=function(){me.event_dialog.hide();loaddoc('Event',me.event_dialog.ev.name);}
div.innerHTML='View Event details, add or edit participants';}
d.widgets['Save'].onclick=function(){var d=me.event_dialog;d.ev.description=d.widgets['Description'].value;if(d.widgets['Cancel Event'].checked)d.ev.event_type='Cancel';else if(d.widgets['Public Event'].checked)d.ev.event_type='Public';me.event_dialog.hide();if(d.cal_ev)
var cal_ev=d.cal_ev;else
var cal_ev=me.set_event(d.ev);cal_ev.save();if(me.cur_view)me.cur_view.refresh();}
this.event_dialog=d;}
this.event_dialog.ev=ev;this.event_dialog.cal_ev=cal_ev?cal_ev:null;this.event_dialog.show();}
Calendar.prototype.add_event=function(){var ev=LocalDB.create('Event');ev=locals['Event'][ev];ev.event_date=dateutil.obj_to_str(this.selected_date);ev.event_hour=this.selected_hour+':00';ev.event_type='Private';this.show_event(ev);}
Calendar.prototype.get_month_events=function(call_back){var me=this;var f=function(r,rt){var el=me.get_daily_event_list(new Date());if($i('today_events_td'))
$i('today_events_td').innerHTML="Today's Events ("+el.length+")";if(me.cur_view)me.cur_view.refresh();if(call_back)call_back();}
var y=this.selected_date.getFullYear();var m=this.selected_date.getMonth();if(!this.events[y]||!this.events[y][m]){$c('webnotes.widgets.event.load_month_events',args={'month':m+1,'year':y},f);}}
Calendar.prototype.get_daily_event_list=function(day){var el=[];var d=day.getDate();var m=day.getMonth();var y=day.getFullYear()
if(this.events[y]&&this.events[y][m]&&this.events[y][m][d]){var l=this.events[y][m][d]
for(var i in l){for(var j in l[i])el[el.length]=l[i][j];}
return el;}
else return[];}
Calendar.prototype.set_event=function(ev){var dt=dateutil.str_to_obj(ev.event_date);var m=dt.getMonth();var d=dt.getDate();var y=dt.getFullYear();if(!this.events[y])this.events[y]=[];if(!this.events[y][m])this.events[y][m]=[];if(!this.events[y][m][d])this.events[y][m][d]=[];if(!this.events[y][m][d][cint(cint(ev.event_hour))])this.events[y][m][d][cint(ev.event_hour)]=[];var l=this.events[y][m][d][cint(ev.event_hour)];var cal_ev=new Calendar.CalEvent(ev,this);l[l.length]=cal_ev;this.has_event[ev.name]=true;return cal_ev;}
Calendar.prototype.refresh=function(viewtype){if(viewtype)
this.viewtype=viewtype;if(this.cur_view.viewtype!=this.viewtype){this.cur_view.hide();this.cur_view=this.views[this.viewtype];this.cur_view.in_home=false;this.cur_view.show();}
else{this.cur_view.refresh(this);}
_c.set_height();}
Calendar.CalEvent=function(doc,cal){this.body=document.createElement('div');var v=locals['Event'][doc.name].description;if(v==null)v='';this.body.innerHTML=v;this.doc=doc;var me=this;this.body.onclick=function(){if(me.doc.name){cal.show_event(me.doc,me);}}}
Calendar.CalEvent.prototype.show=function(vu){var t=this.doc.event_type;this.my_class='cal_event cal_event_'+t;if(this.body.parentNode)
this.body.parentNode.removeChild(this.body);vu.body.appendChild(this.body);var v=this.doc.description;if(v==null)v='';this.body.innerHTML=v;this.body.className=this.my_class;}
Calendar.CalEvent.prototype.save=function(){var me=this;save_doclist('Event',me.doc.name,'Save',function(r){me.doc=locals['Event'][r.docname];_c.calendar.has_event[r.docname]=true;});}
Calendar.View=function(){this.daystep=0;this.monthstep=0;}
Calendar.View.prototype.init=function(cal){this.cal=cal;this.body=$a(cal.body,'div','cal_view_body');this.body.style.display='none';this.create_table();}
Calendar.View.prototype.show=function(){this.get_events();this.refresh();this.body.style.display='block';}
Calendar.View.prototype.hide=function(){this.body.style.display='none';}
Calendar.View.prototype.next=function(){var s=this.cal.selected_date;this.cal.selected_date=new Date(s.getFullYear(),s.getMonth()+this.monthstep,s.getDate()+this.daystep);this.get_events();this.refresh();}
Calendar.View.prototype.prev=function(){var s=this.cal.selected_date;this.cal.selected_date=new Date(s.getFullYear(),s.getMonth()-this.monthstep,s.getDate()-this.daystep);this.get_events();this.refresh();}
Calendar.View.prototype.get_events=function(){this.cal.get_month_events();}
Calendar.View.prototype.add_unit=function(vu){this.viewunits[this.viewunits.length]=vu;}
Calendar.View.prototype.refresh_units=function(){if(isIE)_c.calendar.cur_view.refresh_units_main();else setTimeout('_c.calendar.cur_view.refresh_units_main()',2);}
Calendar.View.prototype.refresh_units_main=function(){for(var r in this.table.rows)
for(var c in this.table.rows[r].cells)
if(this.table.rows[r].cells[c].viewunit)this.table.rows[r].cells[c].viewunit.refresh();}
Calendar.MonthView=function(cal){this.init(cal);this.monthstep=1;this.rows=5;this.cells=7;}
Calendar.MonthView.prototype=new Calendar.View();Calendar.MonthView.prototype.create_table=function(){this.head_wrapper=$a(this.body,'div','cal_month_head');this.headtable=$a(this.head_wrapper,'table','cal_month_headtable');var r=this.headtable.insertRow(0);for(var j=0;j<7;j++){var cell=r.insertCell(j);cell.innerHTML=_c.calendar.weekdays[j];$w(cell,(100/7)+'%');}
this.main=$a(this.body,'div','cal_month_body');this.table=$a(this.main,'table','cal_month_table');var me=this;for(var i=0;i<5;i++){var r=this.table.insertRow(i);for(var j=0;j<7;j++){var cell=r.insertCell(j);cell.viewunit=new Calendar.MonthViewUnit(cell);}}}
Calendar.MonthView.prototype.refresh=function(){var c=this.cal.selected_date;var me=this;var cur_row=0;var cur_month=c.getMonth();var cur_year=c.getFullYear();var d=new Date(cur_year,cur_month,1);var day=1-d.getDay();var d=new Date(cur_year,cur_month,day);this.cal.view_title.innerHTML=month_list_full[cur_month]+' '+cur_year;for(var i=0;i<6;i++){if((i<5)||cur_month==d.getMonth()){for(var j=0;j<7;j++){var cell=this.table.rows[cur_row].cells[j];if((i<5)||cur_month==d.getMonth()){cell.viewunit.day=d;cell.viewunit.hour=8;if(cur_month==d.getMonth()){cell.viewunit.is_disabled=false;if(same_day(this.cal.todays_date,d))
cell.viewunit.is_today=true;else
cell.viewunit.is_today=false;}else{cell.viewunit.is_disabled=true;}}
day++;d=new Date(cur_year,cur_month,day);}}
cur_row++;if(cur_row==5){cur_row=0;}}
this.refresh_units();}
Calendar.DayView=function(cal){this.init(cal);this.daystep=1;}
Calendar.DayView.prototype=new Calendar.View();Calendar.DayView.prototype.create_table=function(){this.main=$a(this.body,'div','cal_day_body');this.table=$a(this.main,'table','cal_day_table');var me=this;for(var i=0;i<12;i++){var r=this.table.insertRow(i);for(var j=0;j<2;j++){var cell=r.insertCell(j);if(j==0){var tmp=time_to_ampm((i*2)+':00');cell.innerHTML=tmp[0]+':'+tmp[1]+' '+tmp[2];$w(cell,'10%');}else{cell.viewunit=new Calendar.DayViewUnit(cell);cell.viewunit.hour=i*2;$w(cell,'90%');if((i>=4)&&(i<=10)){cell.viewunit.is_daytime=true;}}}}}
Calendar.DayView.prototype.refresh=function(){var c=this.cal.selected_date;var me=this;this.cal.view_title.innerHTML=_c.calendar.weekdays[c.getDay()]+', '+c.getDate()+' '+month_list_full[c.getMonth()]+' '+c.getFullYear();var d=c;for(var i=0;i<12;i++){var cell=this.table.rows[i].cells[1];if(same_day(this.cal.todays_date,d))cell.viewunit.is_today=true;else cell.viewunit.is_today=false;cell.viewunit.day=d;}
this.refresh_units();}
Calendar.WeekView=function(cal){this.init(cal);this.daystep=7;}
Calendar.WeekView.prototype=new Calendar.View();Calendar.WeekView.prototype.create_table=function(){this.head_wrapper=$a(this.body,'div','cal_month_head');this.headtable=$a(this.head_wrapper,'table','cal_month_headtable');var r=this.headtable.insertRow(0);for(var j=0;j<8;j++){var cell=r.insertCell(j);$w(cell,(100/8)+'%');}
this.main=$a(this.body,'div','cal_week_body');this.table=$a(this.main,'table','cal_week_table');var me=this;for(var i=0;i<12;i++){var r=this.table.insertRow(i);for(var j=0;j<8;j++){var cell=r.insertCell(j);if(j==0){var tmp=time_to_ampm((i*2)+':00');cell.innerHTML=tmp[0]+':'+tmp[1]+' '+tmp[2];$w(cell,'10%');}else{cell.viewunit=new Calendar.WeekViewUnit(cell);cell.viewunit.hour=i*2;if((i>=4)&&(i<=10)){cell.viewunit.is_daytime=true;}}}}}
Calendar.WeekView.prototype.refresh=function(){var c=this.cal.selected_date;var me=this;this.cal.view_title.innerHTML=month_list_full[c.getMonth()]+' '+c.getFullYear();var d=new Date(c.getFullYear(),c.getMonth(),c.getDate()-c.getDay());for(var k=1;k<8;k++){this.headtable.rows[0].cells[k].innerHTML=_c.calendar.weekdays[d.getDay()]+' '+d.getDate();for(var i=0;i<12;i++){var cell=this.table.rows[i].cells[k];if(same_day(this.cal.todays_date,d))cell.viewunit.is_today=true;else cell.viewunit.is_today=false;cell.viewunit.day=d;}
d=new Date(d.getFullYear(),d.getMonth(),d.getDate()+1);}
this.refresh_units();}
Calendar.ViewUnit=function(){}
Calendar.ViewUnit.prototype.init=function(parent){parent.style.border="1px solid #CCC";this.body=$a(parent,'div',this.default_class);this.parent=parent;var me=this;this.body.onclick=function(){_c.calendar.selected_date=me.day;_c.calendar.selected_hour=me.hour;if(_c.calendar.cur_vu&&_c.calendar.cur_vu!=me){_c.calendar.cur_vu.deselect();me.select();_c.calendar.cur_vu=me;}}
this.body.ondblclick=function(){_c.calendar.add_event();}}
Calendar.ViewUnit.prototype.set_header=function(v){this.header.innerHTML=v;}
Calendar.ViewUnit.prototype.set_today=function(){this.is_today=true;this.set_display();}
Calendar.ViewUnit.prototype.clear=function(){if(this.header)this.header.innerHTML='';while(this.body.childNodes.length)
this.body.removeChild(this.body.childNodes[0]);}
Calendar.ViewUnit.prototype.set_display=function(){var cn='#FFF';var col_tod_sel='#EEE';var col_tod='#FFF';var col_sel='#EEF';if(this.is_today){if(this.selected)cn=col_tod_sel;else cn=col_tod;}else
if(this.selected)cn=col_sel;if(this.header){if(this.is_disabled){this.body.className=this.default_class+' cal_vu_disabled';this.header.style.color='#BBB';}else{this.body.className=this.default_class;this.header.style.color='#000';}
if(this.day&&this.day.getDay()==0)
this.header.style.backgroundColor='#FEE';else
this.header.style.backgroundColor='';}
this.parent.style.backgroundColor=cn;}
Calendar.ViewUnit.prototype.is_selected=function(){return(same_day(this.day,_c.calendar.selected_date)&&this.hour==_c.calendar.selected_hour)}
Calendar.ViewUnit.prototype.get_event_list=function(){var y=this.day.getFullYear();var m=this.day.getMonth();var d=this.day.getDate();if(_c.calendar.events[y]&&_c.calendar.events[y][m]&&_c.calendar.events[y][m][d]&&_c.calendar.events[y][m][d][this.hour]){return _c.calendar.events[y][m][d][this.hour];}else
return[];}
Calendar.ViewUnit.prototype.refresh=function(){this.clear();if(this.is_selected()){if(_c.calendar.cur_vu)_c.calendar.cur_vu.deselect();this.selected=true;_c.calendar.cur_vu=this;}
this.set_display();this.el=this.get_event_list();if(this.onrefresh)this.onrefresh();for(var i in this.el){this.el[i].show(this);}
var me=this;}
Calendar.ViewUnit.prototype.select=function(){this.selected=true;this.set_display();}
Calendar.ViewUnit.prototype.deselect=function(){this.selected=false;this.set_display();}
Calendar.ViewUnit.prototype.setevent=function(){}
Calendar.MonthViewUnit=function(parent){this.header=$a(parent,'div',"cal_month_date");this.default_class="cal_month_unit";this.init(parent);this.onrefresh=function(){this.header.innerHTML=this.day.getDate();}}
Calendar.MonthViewUnit.prototype=new Calendar.ViewUnit();Calendar.MonthViewUnit.prototype.is_selected=function(){return same_day(this.day,_c.calendar.selected_date)}
Calendar.MonthViewUnit.prototype.get_event_list=function(){return _c.calendar.get_daily_event_list(this.day);}
Calendar.DayViewUnit=function(parent){this.default_class="cal_day_unit";this.init(parent);}
Calendar.DayViewUnit.prototype=new Calendar.ViewUnit();Calendar.DayViewUnit.prototype.onrefresh=function(){if(this.el.length<3)this.body.style.height='30px';else this.body.style.height='';}
Calendar.WeekViewUnit=function(parent){this.default_class="cal_week_unit";this.init(parent);}
Calendar.WeekViewUnit.prototype=new Calendar.ViewUnit();Calendar.WeekViewUnit.prototype.onrefresh=function(){if(this.el.length<3)this.body.style.height='30px';else this.body.style.height='';}