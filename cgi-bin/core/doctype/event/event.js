cur_frm.cscript.onload = function(doc, cdt, cdn) {
  var df = get_field('Event', 'Intro HTML', doc.name);
  if(doc.ref_type) {
    ref = repl(cur_frm.cstring.ref_html, {'dt': doc.ref_type, 'dn':doc.ref_name});
  } else var ref = '';
     
  df.options = repl(cur_frm.cstring.intro_html, {'ref': ref});
  refresh_fields('Intro HTML');
}
