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


GraphViewer= function(parent, w, h) {

	this.show_labels = true;
	this.font_size = 10;
	
	if(!parent) {
		this.wrapper = document.createElement('div')
		parent = this.wrapper
	}
	
	this.body = $a(parent, 'div', 'gr_body');
	
	if(w&&h) {
		$w(this.body, w + 'px');
		$w(this.body, h + 'px');
	}
	
	this._y_name = $a(parent, 'div', 'gr_y_name');
	this._x_name = $a(parent, 'div', 'gr_x_name');

	this._y_labels = $a(parent, 'div', 'gr_y_labels');
	this._x_labels = $a(parent, 'div', 'gr_x_labels');
	
	this.legend_area = $a(parent, 'div', 'gr_legend_area');
	this.title_area = $a(parent, 'div', 'gr_title_area');
	
	this.main_area = $a(parent, 'div', 'gr_main_area');
	this.set_horizontal();
	//this.set_vertical();
}
GraphViewer.prototype.clear = function() {
	this.series = [];
	this.xlabels = [];
	this.xtitle = null;
	this.ytitle = null;
}
GraphViewer.prototype.set_vertical = function() {
	this.k_barwidth = 'width';
	this.k_barstart = 'left';
	this.k_barlength = 'height';
	this.k_barbase = 'bottom';
	this.k_bartop = 'top';
	this.k_gridborder = 'borderTop';
	
	this.y_name = this._y_name;
	this.x_name = this._x_name;
	
	this.y_labels = this._y_labels;
	this.x_labels = this._x_labels;
	
	this.vertical = true;
}

GraphViewer.prototype.set_horizontal = function() {
	this.k_barwidth = 'height';
	this.k_barstart = 'top';
	this.k_barlength = 'width';
	this.k_barbase = 'left';
	this.k_bartop = 'right';
	this.k_gridborder = 'borderRight';

	this.y_name = this._x_name;
	this.x_name = this._y_name;
	
	this.y_labels = this._x_labels;
	this.x_labels = this._y_labels;

	this.vertical = false;
}

GraphViewer.prototype.set_title = function(t) {
	this.title_area.innerHTML = t;
}

GraphViewer.prototype.add_series = function(label, color, values, borderColor) {
	var s = new GraphViewer.GraphSeries(this, label);
	s.color = color;
	s.borderColor = borderColor;
	s.data = values;
	this.series[this.series.length] = s;
	//this.xlabels[this.xlabels.length] = label;
}

GraphViewer.prototype.refresh = function() {
	
	//
	this.legend_area.innerHTML = '';
	this.main_area.innerHTML = '';
	this.x_labels.innerHTML = '';
	this.y_labels.innerHTML = '';
	this.x_name.innerHTML = '';
	this.y_name.innerHTML = '';
		
	// get max
	var maxx=null;
	var legendheight = 12;

	for(i=0;i<this.series.length;i++) {
		var series_max = this.series[i].get_max();
		if(!maxx)maxx = series_max;
		if(series_max > maxx)maxx = series_max;
		
		// show series names
		var tmp = $a(this.legend_area, 'div', 'gr_legend');
		tmp.style.backgroundColor = this.series[i].color;
		if(this.series[i].borderColor)
			tmp.style.border = '1px solid ' + this.series[i].borderColor;
		tmp.style.top = (i*(legendheight + 2)) + 'px';
		tmp.style.height= legendheight + 'px';

		var tmp1 = $a(this.legend_area, 'div', 'gr_legend');
		tmp1.style.top = (i*(legendheight + 2)) + 'px';
		tmp1.style.left = '30px';
		$w(tmp1, '80px');
		tmp1.innerHTML = this.series[i].name;
	}
	if(maxx==0)maxx = 1;
	this.maxx = 1.1 * maxx;

	// y - axis grid
	var xfn = fmt_money;
	
	// smart grid
	if(maxx>1) {
		var nchars = (cint(maxx)+'').length;
		var gstep = Math.pow(10, (nchars-1));
		while(flt(maxx / gstep) < 4) {
			gstep = gstep / 2;
		}
	} else {
		var gstep = maxx / 6;
	}
		
	var curstep = gstep;
	
	while(curstep < this.maxx) {
		var gr = $a(this.main_area, 'div', 'gr_grid');
		gr.style[this.k_bartop] = (100-((flt(curstep)/this.maxx) * 100)) + '%';
		gr.style[this.k_barwidth] = '100%';
		gr.style[this.k_gridborder] = '1px dashed #888';
		var ylab = $a(this.y_labels, 'div', 'gr_label');
		ylab.style[this.k_bartop] = (99-((flt(curstep)/this.maxx)*100)) + '%';
		ylab.style[this.k_barstart] = '10%';
		ylab.innerHTML = xfn(curstep);
		curstep += gstep;
	}
	
	if(this.vertical) {	
		this.x_name.innerHTML = this.xtitle;
		middletext(this.y_name, this.ytitle);
	} else {
		middletext(this.x_name, this.xtitle);
		this.y_name.innerHTML = this.ytitle;
	}
	
	// make X units
	this.xunits = [];
	this.xunit_width = (100 / this.xlabels.length);
	if(this.series[0]){
		for(i=0;i<this.xlabels.length;i++) {
			this.xunits[this.xunits.length] = new GraphViewer.GraphXUnit(this, i, this.xlabels[i]);
		}
	}	
}

GraphViewer.GraphSeries= function(graph, name) {
	this.graph = graph;
	this.name = name;
}
GraphViewer.GraphSeries.prototype.get_max = function() {
	var m;
	for(t=0;t<this.data.length;t++) {
		if(!m)m = this.data[t];
		if(this.data[t]>m)m=this.data[t]
	}
	return m;
}

GraphViewer.GraphXUnit= function(graph, idx, label) {
	this.body = $a(graph.main_area, 'div', 'gr_xunit');
	this.body.style[graph.k_barstart] = (idx * graph.xunit_width) + '%';	
	this.body.style[graph.k_barwidth] = graph.xunit_width + '%';
	this.body.style[graph.k_barlength] = '100%';
	this.show(graph, label, idx);
	
	//
	if(graph.show_labels) {
		this.label = $a(graph.x_labels, 'div', 'gr_label');
		this.label.style[graph.k_barstart] = (idx * graph.xunit_width) + '%';
		this.label.style[graph.k_barwidth] = graph.xunit_width + '%';	
		if(graph.vertical) {
			$y(this.label,{height:'100%',top:'10%'});
			this.label.innerHTML = label;
		} else {
			middletext(this.label, label);
		}
	}
}

GraphViewer.GraphXUnit.prototype.show = function(graph, l, idx) {
	var bar_width = (100 / (graph.series.length + 1));
	//if(bar_width>15) bar_width = 15;
	//if(bar_width<20) bar_width = 20;
	start = (100 - (graph.series.length*bar_width)) / 2
	
	for(var i=0;i<graph.series.length; i++) {
		var v = graph.series[i].data[idx];
		var b = $a(this.body, 'div', 'gr_bar');
		b.style[graph.k_barbase] = '0%';
		b.style[graph.k_barstart] = start + '%';
		b.style[graph.k_barwidth] = bar_width + '%';
		b.style[graph.k_barlength] = (v / graph.maxx * 100) + '%';
		if(graph.series[i].color)b.style.backgroundColor = graph.series[i].color;
		if(graph.series[i].borderColor)
			b.style.border = '1px solid ' + graph.series[i].borderColor;
		
		start += bar_width;
	}
}

function middletext(par, t, size) {
	if(!size)size = 10;
	var tb = $a(par, 'div', 'absdiv');
	tb.style.top = ((par.clientHeight - size) / 2) + 'px';
	tb.innerHTML = t;
}