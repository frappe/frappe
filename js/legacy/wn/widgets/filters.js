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

// Fitler object
// pass a list of docfields that need to be set as filters
// creates ranges for dates and number types
//
// ------------- 
// Filter By:
// Label [Input] [[ to [Input]]] [x]
// Label [Input] [[ to [Input]]] [x]
// [select:Add a filter]

wn.widgets.Filters = function(parent, fields) {
	this.fields = fields;
	this.filters = [];
	
	this.make = function() {
		this.filter_area = $a(parent, 'div', 'filters-wrapper')
		this.create_add_fitler_select()
	}
	
	this.create_add_fitler_select = function() {
		
		this.add_btn = $btn(parent, '+ Add a new Filter', this.add_filter);
	}
 	
	this.add_filter = function(df) {
		
	}

	this.get_values = function() {
		var values = {}
		for(var i=0;i<this.fitlers.length;i++) {
			var f = this.filters[i];
			values[f.df.fieldname] = f.field.get_value();
		}
		return values;
	}
	
}


// single fitler - label, input, (input1), delete btn
wn.widgets.SingleFilter = function(parent, docfield) {
	this.parent = parent;
	this.df = docfield;
	
}