Javascript Utilities
====================

AJAX - Server Calls
-------------------

.. function:: $c(command, args, call_back, on_timeout, no_spinner, freeze_msg)

   call a function on the server, where
   
   * `cmd` is the command to the handler
   * `args` dictionary of arguments (form data)
   * `call_back` - function to be called on complete
   * `on_timeout` - function to be called on timeout
   * `no_spinner` - do not show the "Loading..." spinner
   * `freeze_msg` - freeze the user page while showing with the given message

.. function:: $c_obj(doclist, method, arg, call_back, no_spinner, freeze_msg)

   call an object on the server, where:
   
   * `doclist` - the doclist of the calling doc or a string with the name of a Control Doctype
   * `method` - method to be called
   * `arg` - string argument
   * `call_back` - function to be called on completion
   * `no_spinner` - do not show the "Loading..." spinner
   * `freeze_msg` - freeze the user page while showing with the given message

.. function:: $c_obj_csv(doclist, method, arg, call_back, no_spinner, freeze_msg)

   call an object on the server and return the output as CSV.
   
   *Note:* There will be no callback. The output must be a list-in-a-list

.. function:: $c_js(path, callback)

   Load a Javascript library. Path must be relative to the js folder. For example: `widgets/calendar.js`

Title
-----

.. data:: title_prefix

   Standard prefix to the title

.. function:: set_title(t) 

   set Page `title`, if `title_prefix` is set, then appends it to the prefix

Events
------

.. function:: addEvent(ev, fn) {
	
   Add a listener to the given event. Example::
   
      addEvent('click', function(e, target) { .. });

String
------

.. function:: clean_smart_quotes(s)

   Returns string with MS Word "Smart" quotes removed

.. function:: replace_newlines(t)

   Replaces newline charcter \\n with '<br>'

.. function:: esc_quotes(s) 

   Returns string with single quote ' escaped

.. function:: strip(s, chars) 

   Python-like function returns string with leading and lagging characters from `chars` removed.
   If `chars` is null, removes whitespace.

.. function:: lstrip(s, chars) 

   Strips `chars` from left side

.. function:: rstrip(s, chars)

   Strips `chars` from right side

.. function:: repl_all(s, s1, s2) {
	
   Replaces all `s1` to `s2` in `s`
	
.. function:: repl(s, dict) 

   Python-like string replacement. Example::
   
     s = repl("Hello %(name)s, welcome to %(location)s", {name:'ABC', location:'Mumbai'});
   
.. function:: esc_quotes(s) 

   Returns string with single quote ' escaped

.. function:: strip(s, chars) 

   Python-like function returns string with leading and lagging characters from `chars` removed.
   If `chars` is null, removes whitespace.

.. function:: lstrip(s, chars) 

   Strips `chars` from left side

.. function:: rstrip(s, chars)

   Strips `chars` from right side

.. function:: repl_all(s, s1, s2) {
	
   Replaces all `s1` to `s2` in `s`
	
.. function:: repl(s, dict) 

   Python-like string replacement. Example::
   
     s = repl("Hello %(name)s, welcome to %(location)s", {name:'ABC', location:'Mumbai'});


Lists
-----

.. function:: in_list(list, item) 

   Returns true if `item` is in `list`

.. function:: inList(list, item) 

   Returns true if `item` is in `list`. Same as `in_list`

.. function:: has_common(list1, list2) 

   Returns true if `list1` and `list2` has common items

.. function add_lists(l1, l2) 

   Returns `l1` + `l2`

Dictionaries
------------

.. function:: keys(obj)

   Python-like function returns keys of a dictionary

.. function:: values(obj)

   Python-like function returns values of a dictionary

.. function:: copy_dict(d) 

   Makes a copy of the dictionary

.. function docstring(obj):: 

   Converts a dictionary to string
   
Datatype Conversion
-------------------

.. function:: cint(v, def)

   Convert a value to integer, if NaN, then return `def`

.. function:: cstr(s) 

   Convet to string

.. function:: flt(v,decimals) 

   Convert to float, with `decimal` places

.. function:: fmt_money(v)

   Convert number to string with commas for thousands, millions etc and 2 decimals. Example::
   
     fmt_money(2324); // equals '2,324.00'

.. function:: is_null(v) 

   Returns true if value is null or empty string.
   Returns false is value is 0

.. function:: d2h(d)

   Convert decimal to hex

.. function:: h2d(h)

   Convert hex to decimal
   
DOM Manipulation
----------------

.. function:: $i(id)

   Shortcut for document.getElementById(id). Returns the element of the given ID

.. function:: $a(parent, newtag, className, style) 

   Add element to the given `parent`. Example::
   
      div = $a(body, 'div', '', {padding: '2px'});

.. function:: $a_input(parent, in_type, attributes, style) 

   Add and INPUT element to the given parent, with given attributes (Fix for IE6 since it does not accept
   `type`). Example::

      chk = $a_input(body, 'checkbox', null, {border: '0px'});

Style
-----

.. function:: $y(ele, s)

   Set Element style. Example::
   
      $y(div,{height:'4px'});
      
.. function:: $dh(d) 

   Hide element, set `display` = 'none'

.. function:: $ds(d)

   set `display` = 'block' (Show element)

.. function:: $di(d)

   set `display` = 'inline' (Show element)

.. function:: $op(e,w)

   Same as :func:`set_opacity`
   
.. function:: set_style(txt) 

      Declare css classes in txt. Example::
      
          set_style('div.myclass { width: 400px }');


.. function:: set_opacity(ele, opacity)

   Set the opacity property of the element 
   opacity between 0 and 100
   
   Same As: $op(e,w)

.. function:: animate(ele, style_key, from, to, callback)

   Animate transition of style property

.. function:: get_darker_shade(col, factor)

   Get a darker shade of the given colour, `col` in HEX, `factor` between 0 and 1


Tables
------

.. function:: make_table(parent, nr, nc, table_width, widths, cell_style) 

   Make a new table in parent with 
      
   * rows `nr`
   * columns `nc`
   * with columns with widths `widths`
   * cell with default style `cell_style`
   
   Example::
   
      var t = make_table(div, 5, 2, '400px', ['100px', '300px'], {padding: '2px'})

.. function:: append_row(t) 

   Append a new row to the table with same number of columns as the first row

.. function:: $td(t,r,c) 

   Returns table cell. Shortcut for t.rows[r].cells[c]

.. function:: $sum(t, cidx) {
	
   Returns sum of values in a table column

.. function:: $yt(tab, r, c, s) 

   Set style on tables with wildcards, Examples::
   
      // hilight row 3
      $yt(t, 3, '*', {backgroundColor:'#EEE'})

      // border to all cells
      $yt(t, '*', '*', {border:'1px solid #000'})

Select Element
--------------

.. function:: empty_select(s) 

   Empty all OPTIONs of the SELECT (or SelectWidget) element

.. function:: sel_val(sel) 

   Returns the selected value of the given SELECT (or SelectWidget) element

.. function:: add_sel_options(s, list, sel_val, o_style) 

   Adds options to the SELECT (or SelectWidget) element s, where sel_val is the default selected value
   
Positioning
-----------

.. function:: objpos(obj)

   Returns {x: `x-cord`, y:`y-cord`} 
   co-ordinates of the given object (for absolute positioning)
    

.. function:: get_screen_dims() {

   Returns {w: `width`, h:`height`} of the screen 

URL
---

.. function:: get_url_arg(name) 

   Return the value of the argument `name` from the URL
   
User Image
----------

.. function:: set_user_img(img, username)

   Sets the user image or No Image tag to the given `img`

Miscelleanous
-------------

.. function:: $s(ele, v, ftype, fopt) 

   Add the value to the Element `ele` based on `fieldtype` and `fieldoptions`
   
   * Covnerts `Link` type to hyperlink
   * Converts `Date` in user format
   * Converts `Check` to image with check

.. function:: validate_email(id) 

   Returns true for a valid email

.. function ie_refresh(e):: 

   Hide element `e`, show element `e`

.. function:: DocLink(p, doctype, name, onload) 

   Creates a hyperlink to load the record (`doctype`, `name`)

.. function:: doc_link(p, doctype, name, onload) 

   Creates a hyperlink to load the record (`doctype`, `name`). Same as DocLink
