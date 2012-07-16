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

wn.provide('wn.meta.docfield_map');
wn.provide('wn.meta.docfield_list');
wn.provide('wn.meta.doctypes');

$.extend(wn.meta, {
	// build docfield_map and docfield_list
	add_field: function(df) {
		wn.provide('wn.meta.docfield_map.' + df.parent);
		wn.meta.docfield_map[df.parent][df.fieldname || df.label] = df;
		
		if(!wn.meta.docfield_list[df.parent])
			wn.meta.docfield_list[df.parent] = [];
			
		// check for repeat
		for(var i in wn.meta.docfield_list[df.parent]) {
			var d = wn.meta.docfield_list[df.parent][i];
			if(df.fieldname==d.fieldname) 
				return; // no repeat
		}
		wn.meta.docfield_list[df.parent].push(df);
	},
	get_docfield: function(dt, fn, dn) {
		if(dn && local_dt[dt] && local_dt[dt][dn]){
			return local_dt[dt][dn][fn];
		} else {
			return wn.meta.docfield_map[dt][fn];
		}
	}
});