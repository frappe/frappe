cur_frm.cscript.refresh = function(doc, cdt, cdn) {
  if(doc.from_doctype) {
      get_field(doc.doctype, 'from_doctype', doc.name).permlevel = 1;
      refresh_field('from_doctype');

      get_field(doc.doctype, 'to_doctype', doc.name).permlevel = 1;
      refresh_field('to_doctype');
  }
}
