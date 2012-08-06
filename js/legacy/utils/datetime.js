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

// Date

function same_day(d1, d2) {
	if(d1.getFullYear()==d2.getFullYear() && d1.getMonth()==d2.getMonth() && d1.getDate()==d2.getDate())return true; else return false;
}
var month_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var month_last = {1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31}
var month_list_full = ['January','February','March','April','May','June','July','August','September','October','November','December'];

var week_list = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
var week_list_full = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

function int_to_str(i, len) {
	i = ''+i;
	if(i.length<len)for(c=0;c<(len-i.length);c++)i='0'+i;
	return i
}

wn.datetime = {
	
	str_to_obj: function(d) { 
		if(typeof d=="object") return d;
		if(!d) return new Date(); 
		var tm = [null, null];
		if(d.search(' ')!=-1) {
			var tm = d.split(' ')[1].split(':');
			var d = d.split(' ')[0];
		}
		if(d.search('-')!=-1) {
			var t = d.split('-'); return new Date(t[0],t[1]-1,t[2],tm[0],tm[1]); 
		} else if(d.search('/')!=-1) {
			var t = d.split('/'); return new Date(t[0],t[1]-1,t[2],tm[0],tm[1]); 
		} else {
			return new Date();
		}
	},

	obj_to_str: function(d) { 
		if(typeof d=='string') return d;
		return d.getFullYear() + '-' + int_to_str(d.getMonth()+1,2) + '-' + int_to_str(d.getDate(),2); 
	},
	
	obj_to_user: function(d) { 
		return dateutil.str_to_user(dateutil.obj_to_str(d)); 
	},
	
	get_diff: function(d1, d2) { 
		if(typeof d1=='string') d1 = dateutil.str_to_obj(d1);
		if(typeof d2=='string') d2 = dateutil.str_to_obj(d2);
		return ((d1-d2) / 86400000); 
	},
	
	get_day_diff: function(d1, d2) {
		return dateutil.get_diff(new Date(d1.getYear(), d1.getMonth(), d1.getDate(), 0, 0), 
			new Date(d2.getYear(), d2.getMonth(), d2.getDate(), 0, 0))
	},
	
	add_days: function(d, days) { 
		var dt = dateutil.str_to_obj(d);
		var new_dt = new Date(dt.getTime()+(days*24*60*60*1000));
		return dateutil.obj_to_str(new_dt);
	},
	
	add_months: function(d, months) {
		dt = dateutil.str_to_obj(d)
		new_dt = new Date(dt.getFullYear(), dt.getMonth()+months, dt.getDate())
		if(new_dt.getDate() != dt.getDate()) {
			// month has changed, go the last date of prev month
			return dateutil.month_end(new Date(dt.getFullYear(), dt.getMonth()+months, 1))
		}
		return dateutil.obj_to_str(new_dt);
	},
	
	month_start: function() { 
		var d = new Date();
		return d.getFullYear() + '-' + int_to_str(d.getMonth()+1,2) + '-01';
	},
	
	month_end: function(d) { 
		if(!d)var d = new Date(); 
		var m = d.getMonth() + 1; 
		var y = d.getFullYear();
		
		last_date = month_last[m];
		if(m==2 && (y % 4)==0 && ((y % 100)!=0 || (y % 400)==0)) // leap year test
			last_date = 29;
		return y+'-'+int_to_str(m,2)+'-'+last_date;
	},
	
	get_user_fmt: function() {
		var t = sys_defaults.date_format;
		if(!t) t = 'dd-mm-yyyy';
		return t;
	},
	
	str_to_user: function(val, no_time_str) {
		var user_fmt = dateutil.get_user_fmt();
		var time_str = '';
		//alert(user_fmt);
		
		
		if(val==null||val=='')return null;
		
		// separate time string if there
		if(val.search(':')!=-1) {
			var tmp = val.split(' ');
			if(tmp[1])
				time_str = ' ' + tmp[1];
			var d = tmp[0];
		} else {
			var d = val;
		}

		if(no_time_str)time_str = '';

		// set to user fmt
		d = d.split('-');
		if(d.length==3) {
			if(user_fmt=='dd-mm-yyyy')
				val =  d[2]+'-'+d[1]+'-'+d[0] + time_str;
			else if(user_fmt=='dd/mm/yyyy')
				val =  d[2]+'/'+d[1]+'/'+d[0] + time_str;
			else if(user_fmt=='yyyy-mm-dd')
				val =  d[0]+'-'+d[1]+'-'+d[2] + time_str;
			else if(user_fmt=='mm/dd/yyyy')
				val =  d[1]+'/'+d[2]+'/'+d[0] + time_str;
			else if(user_fmt=='mm-dd-yyyy')
				val =  d[1]+'-'+d[2]+'-'+d[0] + time_str;
		}

		return val;
	},
	
	full_str: function() { 
		var d = new Date();
		return d.getFullYear() + '-' + (d.getMonth()+1) + '-' + d.getDate() + ' '
		+ d.getHours()  + ':' + d.getMinutes()   + ':' + d.getSeconds();
	},
	
	user_to_str: function(d) {
		var user_fmt = this.get_user_fmt();
		
		if(user_fmt=='dd-mm-yyyy') {
			var d = d.split('-');
			return  d[2]+'-'+d[1]+'-'+d[0];
		}
		else if(user_fmt=='dd/mm/yyyy') {
			var d = d.split('/');
			return  d[2]+'-'+d[1]+'-'+d[0];
		}
		else if(user_fmt=='yyyy-mm-dd') {
			return d;
		}
		else if(user_fmt=='mm/dd/yyyy') {
			var d = d.split('/');
			return  d[2]+'-'+d[0]+'-'+d[1];
		}
		else if(user_fmt=='mm-dd-yyyy') {
			var d = d.split('-');
			return  d[2]+'-'+d[0]+'-'+d[1];
		}
	},
	
	global_date_format: function(d) {
		if(d.substr) d = this.str_to_obj(d);
		return nth(d.getDate()) + ' ' + month_list_full[d.getMonth()] + ' ' + d.getFullYear();
	},

	get_today: function() {
		var today = new Date();
		var m = (today.getMonth()+1)+'';
		if(m.length==1)m='0'+m;
		var d = today.getDate()+'';
		if(d.length==1)d='0'+d;
		return today.getFullYear()+'-'+m+'-'+d;
	},

	get_cur_time: function() {
		// returns current time in hh:mm string
		var d = new Date();
		var hh = d.getHours() + ''
		var mm = cint(d.getMinutes()/5)*5 + ''
		
		return (hh.length==1 ? '0'+hh : hh) + ':' + (mm.length==1 ? '0'+mm : mm);
	}
}

wn.datetime.only_date = function(val) {
	if(val==null||val=='')return null;
	if(val.search(':')!=-1) {
		var tmp = val.split(' ');
		var d = tmp[0].split('-');
	} else {
		var d = val.split('-');
	}
	if(d.length==3) 
		val =  d[2]+'-'+d[1]+'-'+d[0];
	return val;
}


// Time

wn.datetime.time_to_ampm = function(v) {
	if(!v) {
		var d = new Date();
		var t = [d.getHours(), cint(d.getMinutes()/5)*5 + '']
	} else {
		var t = v.split(':');
	}

	if(t.length!=2){
		show_alert('[set_time] Incorect time format');
		return;
	}
	
	if(t[1].length==1) t[1]='0' + t[1];
	
	if(cint(t[0]) == 0) var ret = ['12', t[1], 'AM'];
	else if(cint(t[0]) < 12) var ret = [cint(t[0]) + '', t[1], 'AM'];
	else if(cint(t[0]) == 12) var ret = ['12', t[1], 'PM'];
	else var ret = [(cint(t[0]) - 12) + '', t[1], 'PM'];
		
	return ret;
}

wn.datetime.time_to_hhmm = function(hh,mm,am) {
	if(am == 'AM' && hh=='12') {
		hh = '00';
	} else if(am == 'PM' && hh!='12') {
		hh = cint(hh) + 12;
	}
	if(!mm) mm='00';
	if(!hh) hh='00';

	return hh + ':' + mm;
}

/*
 * JavaScript Pretty Date
 * Copyright (c) 2011 John Resig (ejohn.org)
 * Licensed under the MIT and GPL licenses.
 */

// Takes an ISO time and returns a string representing how
// long ago the date represents.
function prettyDate(time){
	if(!time) return ''
	var date = time;
	if(typeof(time)=="string")
		date = new Date((time || "").replace(/-/g,"/").replace(/[TZ]/g," ").replace(/\.[0-9]*/, ""));
	
	var diff = (((new Date()).getTime() - date.getTime()) / 1000),
	day_diff = Math.floor(diff / 86400);
	
	if ( isNaN(day_diff) || day_diff < 0 )
		return '';
			
	return day_diff == 0 && (
			diff < 60 && "just now" ||
			diff < 120 && "1 minute ago" ||
			diff < 3600 && Math.floor( diff / 60 ) + " minutes ago" ||
			diff < 7200 && "1 hour ago" ||
			diff < 86400 && Math.floor( diff / 3600 ) + " hours ago") ||
		day_diff == 1 && "Yesterday" ||
		day_diff < 7 && day_diff + " days ago" ||
		day_diff < 31 && Math.ceil( day_diff / 7 ) + " weeks ago" ||
		day_diff < 365 && Math.ceil( day_diff / 30) + " months ago" ||
		"more than " + Math.floor( day_diff / 365 ) + " year(s) ago";
}

// If jQuery is included in the page, adds a jQuery plugin to handle it as well
if ( typeof jQuery != "undefined" )
	jQuery.fn.prettyDate = function(){
		return this.each(function(){
			var date = prettyDate(this.title);
			if ( date )
				jQuery(this).text( date );
		});
	};

var comment_when = prettyDate;
wn.datetime.comment_when = prettyDate;

// globals (deprecate)
var date = dateutil = wn.datetime;
var get_today = wn.datetime.get_today
var time_to_ampm = wn.datetime.time_to_ampm;
var time_to_hhmm = wn.datetime.time_to_hhmm;
var only_date = wn.datetime.only_date;
