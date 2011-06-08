Client Side Cookbook
====================

Standard Patterns for Client Side Scripts

Fetch customer cell no and email id based on name
--------------------------------------------------

This can be implemented using the standard fetch pattern::

  cur_frm.add_fetch('customer', 'email_id', 'customer_email');
  cur_frm.add_fetch('customer', 'cell_no', 'customer_cell_no');


Form Events (Triggers)
----------------------

Standard Form-level Triggers are

* refresh - This is called whenever a new record is loaded, or a record is opened, or when a record is saved
* onload - This is called the first time a record is loaded
* setup - This is called the first time a Form is loaded

Some Examples::

  cur_frm.cscript.refresh = function(doc, dt, dn) {
     // set contextual help
     
     cur_frm.clear_tip();
     if(doc.city && !doc.location) cur_frm.set_tip("Its always a good idea to add location to the city");
  }

Accessing / Updating Field Objects
----------------------------------

Every input / field in the Form is an instance of the :class:`_f.Field`. The reference to the field object
can be got using `cur_frm.fields_dict` property. This is a dictionary that contains reference to all field
objects by name or label (in case there is no name). 

Properties of the field can be set by setting the `df` dictionary (which represents the `DocField`). Example::

  var f = cur_frm.fields_dict['first_name']
  f.df.hidden = 1;
  f.refresh();

Field Events (Triggers)
-----------------------

Field `onchange` triggers can be set by declaring a function in the `cur_frm.cscript` object (namespace). The
function will be called when the onchange event will be triggered. The function will be passed 3 parameters

* doc - reference to the current main record
* dt - reference to the DocType (this will be different to `doc.doctype` in case of a child (table) trigger)
* dn - reference to the DocType (this will be different to `doc.name` in case of a child (table) trigger)

Example::

  cur_frm.cscript.first_name(doc, dt, dn) {
  	if(doc.first_name.length < 3) {
  	   msgprint("First Name should atleast be 3 characters long.")	
  	}
  }


Overloading Link Field queries
------------------------------

If a filter is to be added to validate values that can be set by `Link` fields, it is necessary to
overload the exiting query method. This can be done by setting the `get_query` method on 
the `Field` object. Example::

   // standard field
   cur_frm.fields_dict['test_link'].get_query = function(doc,dt,dn) {
      return "SELECT tabDocType.name FROM tabDocType WHERE IFNULL(tabDocType.issingle,0)=0 AND tabDocType.name LIKE '%s'"
   }
   
   // field in a grid
   cur_frm.fields_dict['test_grid'].grid.get_field('my_link').get_query = function(doc,dt,dn) {
      return "SELECT tabDocType.name FROM tabDocType WHERE IFNULL(tabDocType.issingle,0)=0 AND tabDocType.name LIKE '%s'"
   }   

Setting contextutal help (Tips)
-------------------------------

Contextual help can be set using the :meth:`_f.Frm.set_tip`, :meth:`_f.Frm.append_tip`, :meth:`_f.Frm.clear_tip`
methods. See Examples::

  cur_frm.cscript.refresh = function(doc, doctype, docname) {
  	cur_frm.clear_tip("")
    if(doc.status="Draft") {
      cur_frm.set_tip("This is a Draft, to publish, please check on 'Published' before saving")
    }
    if(doc.is_popular="Yes") {
      cur_frm.append_tip("This post is popular!")	
    }
  }

Custom UI using the HTML Field
------------------------------

Custom UI Objects can be added to forms by using the HTML field. The object can be added in the form wrapper
and reset with latest values on the `refresh` event. Example::

  cur_frm.cscript.refresh = function(doc, dt, dn) {
     var cs = cur_frm.cscript;
     if(!cs.my_object) {
     	
     	// lets add a listing
        cs.my_object = new Listing();
        ..
        ..	
     }
     
     cs.my_object.refresh();
  }

Useful API Methods
------------------

.. function:: get_children(child_dt, parent, parentfield, parenttype)

   Get list of child records for the given parent record where:
   
   * child_dt is the DocType of the child type
   * parent is ths name of the parent record
   * parentfield is the fieldname of the child table in the parent DocType
   * parenttype is the type of the Parent `DocType`

.. function:: get_field(doctype, fieldname, docname)

   Get the field metadata (`DocField` format) for the given field and given record.
   
   **Note:** Separate metadata is maintained for each field of each record. This is because metadata
   can be changed by a script only for one record. For example, a field may be hidden in record A but
   visible in record B. Hence same metadata cannot be referenced for the two records. Example::
   
      f = get_field(doc.doctype, 'first_name', doc.name);
      f.hidden = 1;
      refresh_field('first_name');

.. function:: get_server_fields(method, arg, table_field, doc, dt, dn, allow_edit, call_back)

   Update the values in the current record by calling a remote method. Example Client Side::
   
      cur_frm.cscript.contact_person = function(doc, cdt, cdn) {
        if(doc.contact_person) {
          var arg = {'customer':doc.customer_name,'contact_person':doc.contact_person};
          get_server_fields('get_contact_details',docstring(arg),'',doc, cdt, cdn, 1);
        }
      }
      
   Server side version::
   
      def get_contact_details(self, arg):
        arg = eval(arg)
        contact = sql("select contact_no, email_id from `tabContact` where contact_name = '%s' and customer_name = '%s'" %(arg['contact_person'],arg['customer']), as_dict = 1)
        ret = {
          'contact_no'       :    contact and contact[0]['contact_no'] or '',
          'email_id'         :    contact and contact[0]['email_id'] or ''
        }
        return str(ret)   

.. function:: $c_get_values(args, doc, dt, dn, user_callback) 

   Similar to get_server_fields, but no serverside required::
   
      cur_frm.cscript.item_code = function(doc, dt, dn) {
        var d = locals[dt][dn];

        $c_get_values({
          fields:'description,uom'       // fields to be updated
          ,table_field:'sales_bom_items'           // [optional] if the fields are in a table
          ,select:'description,stock_uom' // values to be returned
          ,from:'tabItem'
          ,where:'name="'+d.item_code+'"'
        }, doc, dt, dn);
      }
   
   
.. function:: set_multiple(dt, dn, dict, table_field)

   Set mutliple values from a dictionary to a record. In case of Table, pass `tablefield`
   
.. function:: refresh_many(flist, dn, table_field)

   Refresh multiple fields. In case of Table, pass `tablefield`

.. function:: refresh_field(n, docname, table_field)

   Refresh a field widget. In case of a table record, mention the `table_field` and row ID `docname`

.. function:: set_field_tip(fieldname, txt)

   Set `txt` comment on a field

.. function:: set_field_options(n, options)

   Set `options` of a field and `refresh`

.. function:: set_field_permlevel(n, permlevel)

   Set `permlevel` of a field and `refresh`

.. function:: hide_field(n)

   Hide a field of fieldname `n` or a list of fields `n`

.. function:: unhide_field(n)

   Unhide a field of fieldname `n` or a list of fields `n`


Using Templates
---------------

The standard Form UI Engine can be overridden using the templates. The `template` is HTML code and can be
set in the `template` field of the DocType. To render fields in the template, Element IDs must be set in a 
specific pattern. The pattern is

* frm_[DocType]_[fieldname]

See Example::
  
  <h1>Contact Form</h1>
  <table>
    <tr>
      <td>First Name</td>
      <td id="frm_Contact_first_name"></td>
    </tr>
    <tr>
      <td>Last Name</td>
      <td id="frm_Contact_last_name"></td>
    </tr>
    <tr>
      <td>Email ID</td>
      <td id="frm_Contact_email"></td>
    </tr>
    <tr>
      <td></td>
      <td><button onclick="cur_frm.save('Save', function() { loadpage('Thank You'); })">Save</button></td>
    </tr>
  </table>
