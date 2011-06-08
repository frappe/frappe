Form Widget API
===============

Scripting Forms
----------------

Custom scripts can be written in forms by writing events in "Client Script" / "Client Script Core" in the
DocType. Some conventions for writing client scripts

* All functions should be written in the namespace `cur_frm.cscript`. This namespace is set aside
  for customized client scripts
* `cur_frm` is the global variable that represents the Current Form that is open.

See Examples

Form Container Class
--------------------

.. data:: _f

   Namespace for the Form Widget
   
.. data:: _f.frm_con

   Global FrmContainer. There is only one instance of the Form Container

.. function:: _f.get_value(dt, dn, fn)

   Returns the value of the field `fn` from DocType `dt` and name `dn`
   
.. function:: _f.get_value(dt, dn, fn, v)

   Sets value `v` in the field `fn` of the give `dt` and `dn`
   
   * Will also set the record as __unsaved = 1
   * Will refresh the display so that the record is set as "Changes are not saved"

.. class:: _f.FrmContainer

   This is the object that contains all Forms. The Form Container contains the page header and Form toolbar
   that is refreshed whenever a new record is shown.
   
   .. attribute:: head
   
      Element representing the header of the form.
      
   .. attribute:: body
   
      Element represnting the page body
      
   .. method:: show_head()
   
      Show the head element
      
   .. method:: hide_head()
   
      Show the head element
      
   .. method:: add_frm(doctype, onload, opt_name)
   
      Called internally by :func:`loaddoc`. Adds a new Form of type `doctype` in the FrmContainer.
      
Form Class
----------

.. class:: _f.Frm
      
   Each doctype has a Frm object. When records are loaded on the Frm object, fields inside the form are
   refreshed
   
   .. attribute:: doctype
   
      `doctype` of the current form
      
   .. attribute:: docname
   
      `name` of the current record

   .. attribute:: fields
   
      List of all `Field` objects in the form
      
   .. attribute:: fields_dict
   
      Dictionary of all `Field` objects in the form, identified by the `fieldname` or `label` (if no fieldname)
      exists

   .. attribute:: sections
   
      List of all sections known by section id (`sec_id`). (Id because Sections may not have headings / labels)
      
   .. attribute:: sections_by_label
   
      Dictionary of all sections by label. This can be used to switch to a particular section. Example::
      
         cur_frm.set_section(cur_frm.sections_by_label['More Details'].sec_id);

   .. method:: show()
   
      Show the form
      
   .. method:: hide()
   
      Hide the form
   
   .. method:: sec_section(sec_id)
   
      Show the section identified by
   
   .. method:: refresh()
   
      Refresh the current form. It will
      
      * Check permission
      * If the record is changed, load the new record data
      * Run 'refresh' method
      * Refresh all fields
      * Show the form
      
   .. method:: refresh_fields()
   
      Will refresh all fields
      
   .. method:: refresh_dependancy()
   
      Will refresh hide / show based on 'depends_on'
   
   .. method:: save(save_action, call_back)
   
      Will save the current record (function called from the "Save" button)
      
      save_action can be `Save`, `Submit`, `Cancel`
      
   .. method:: print_doc()
   
      Show the `Print` dialog
      
   .. method:: email_doc()
   
      Shows the `Email` dialog
      
   .. method:: copy_doc()
   
      Copy the current record
      
   .. method:: reload_doc()
   
      Reload the current record from the server
      
   .. method:: amend_doc()
   
      Amend the current Cancelled record
      
   .. method:: check_required(dt, dn)
   
      Checks whether all mandatory fields are filled
   
   .. method:: runscript(scriptname, callingfield, onrefresh)
   
      Run a server-side script where Trigger is set as `Server`. The server method is identified by
      `scriptname`
      
   .. method:: runclientscript(caller, cdt, cdn)
   
      Run a client script identified by the calling fieldname `caller`. `cdt` and `cdn` are the
      id of the calling `DocType and `name`
      
   .. method:: set_tip(txt)
   
      Clear existing tips and set a new tip (contextual help) in the Form
      
   .. method:: append_tip(txt)
   
      Add another tip to the existing tips
      
   .. method:: clear_tip()
   
      Clear all tips
      
Field Class
-----------

.. class:: _f.Field()

  .. attribute:: df
  
     the `df` attribute represents the Field data. Standard Field properties are
     
     * fieldname
     * fieldtype
     * options
     * permlevel
     * description
     * reqd
     * hidden
     * search_index
     
     Example::
     
        var field = cur_frm.fields_dict['first_name']
        field.df.reqd = 1;
        field.refresh();

  .. attribute:: wrapper
  
     Wrapping DIV Element
     
  .. attribute:: label_area
  
     HTML Element where the label of the field is printed
     
  .. attribute:: disp_area
  
     HTML Element where the value of the field is printed in "Read" mode

  .. attribute:: input_area
  
     HTML Element where the widget is placed in "Write" mode

  .. attribute:: comment_area
  
     HTML Element where the comment (description) is printed

  .. attribute:: parent_section
  
     If the `section_style` of the doctype is `Tray` or `Tabbed`, then this represents the SectionBreak
     object in which this field is. This is used to switch to the section in case of an error.

  .. method:: get_status()
  
     Retuns the whether the field has permission to `Read`, `Write` or `None`
  
  .. method:: set(v)
  
     Sets a value to the field. Value is set in `locals` and the widget
     
  .. method:: run_trigger()
  
     Runs any client / server triggers. Called `onchange`

Grid Class
----------

.. class:: _f.FormGrid()

   The FromGrid Class inherits from the Grid class. The Grid class was designed to be a generic INPUT.
   
   * The metadata of the grid is defined by the `DocType` of the `Table` field.
   * Each column of the grid represents a field.
   * Each row of the grid represents a record

   **Grid Types**
   
   There are two type of Grids:
   
   #. Standard: Where fields can be edited within the cell
   #. Simple: Where fields are edited in a popup Dialog box. A Simple Grid can be created by setting the 
      `default` property of the Table field to "Simple"

   When the user clicks on an editable Grid cell, it adds an `Field` object of that particular column to the
   cell so that the user can edit the values inside the cell. This `Field` object is known as the `template`
   The `template` can be accessed by the `get_field` method
   
   .. method:: get_field(fieldname)
   
      Returns the `template` (`Field` object) identified by `fieldname`
      
   .. method:: refresh()
   
      Refresh all data in the Grid

Examples
--------

