// Calculator 
// ----------
_r.calc_dialog = null;
_r.show_calc = function(tab, colnames, coltypes, add_idx) {
	if(!add_idx) add_idx = 0;
	if(!tab || !tab.rows.length) { msgprint("No Data"); return; }
	
	if(!_r.calc_dialog) {
		var d = new Dialog(400,400,"Calculator")
		d.make_body([
			['Select','Column']
			,['Data','Sum']
			,['Data','Average']
			,['Data','Min']
			,['Data','Max']
		])
		d.widgets['Sum'].readonly = 'readonly';
		d.widgets['Average'].readonly = 'readonly';
		d.widgets['Min'].readonly = 'readonly';
		d.widgets['Max'].readonly = 'readonly';
		d.widgets['Column'].onchange = function() {
			d.set_calc();
		}
		d.set_calc = function() {
			// get the current column of the data table
			var cn = sel_val(this.widgets['Column']);
			var cidx = 0; var sum=0; var avg=0; var minv = null; var maxv = null;
			for(var i=0;i<this.colnames.length;i++) {if(this.colnames[i]==cn){ cidx=i+add_idx; break; } }
			for(var i=0; i<this.datatab.rows.length; i++) {
				var c = this.datatab.rows[i].cells[cidx];
				var v = c.div ? flt(c.div.innerHTML) : flt(c.innerHTML);
				sum += v;
				if(minv == null) minv = v;
				if(maxv == null) maxv = v;
				if(v > maxv)maxv = v;
				if(v < minv)minv = v;
			}
			d.widgets['Sum'].value = fmt_money(sum);
			d.widgets['Average'].value = fmt_money(sum / this.datatab.rows.length);
			d.widgets['Min'].value = fmt_money(minv);
			d.widgets['Max'].value = fmt_money(maxv);
			_r.calc_dialog = d;
		}
		d.onshow = function() {
			// set columns
			var cl = []; 
			for(var i in _r.calc_dialog.colnames) {
				if(in_list(['Currency','Int','Float'],_r.calc_dialog.coltypes[i])) 
					cl.push(_r.calc_dialog.colnames[i]);
			}
			if(!cl.length) {
				this.hide();
				alert("No Numeric Column");
				return;
			}
			var s = this.widgets['Column'];
			empty_select(s);
			add_sel_options(s, cl);
			if(s.inp)s.inp.value = cl[0];
			else s.value = cl[0];
			this.set_calc();
		}
		_r.calc_dialog = d;
	}
	_r.calc_dialog.datatab = tab;
	_r.calc_dialog.colnames = colnames;
	_r.calc_dialog.coltypes = coltypes;
	_r.calc_dialog.show();
}
