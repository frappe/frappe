Page Structure and Navigation
=============================

Page Structure
--------------

.. data:: page_body

   global reference to the :class:`Body`

.. class:: Body()

   Created by app.js

   .. attribute:: header
   
      Head element

   .. attribute:: footer
   
      Footer element

   .. attribute:: left_side_bar
   
      Left Sidebar Element

   .. attribute:: right_side_bar
   
      Right Sidebar Element
      
   .. attribute:: center
   
      Center content Element
      
   .. attribute:: pages
   
      Dictionary of pages by label
      
   .. attribute:: cur_page
   
      Current page
      
   .. method:: add_page(label, onshow)
   
      Returns a new page (DIV) with label. Optionally `onshow` function will be called when the page is shown
   
   .. method:: change_to(page_name)
   
      Switch to the given page

Opening existing resources (Pages, Forms etc)
---------------------------------------------

.. function:: loaddoc(doctype, name, onload, menuitem) 

   Open an exiting record (`doctype`, `name`) from the server or :term:`Locals`
   
   Optionally you can specify onload method and menuitem. If menuitem is specified, it will show the menuitem
   as selected whenever the record is reloaded.
   
.. function:: new_doc(doctype, onload)

   Open a new record of type `doctype`
   
.. function:: loadpage(page_name, call_back, menuitem)

   Open the page specified by `page_name`. If menuitem is specified, it will show the menuitem
   as selected whenever the page is reloaded.
   
.. function:: loadreport(doctype, rep_name, onload, menuitem, reset_report)

   Open the report builder of the given `doctype`. Optionally if `rep_name` is specified, it will
   open the corresponding :term:`Search Criteria` identified by `criteria_name`
   
History
-------

History is maintained by framgments using the Really Simple History (rsh) library

.. data:: nav_obj

   global reference to the history object
   
.. function:: nav_obj.open_notify(type, p1, p2)

   Notify of a new page opening. Add to history   
   * `type` is either - Form, Report or Page
   * `p1` is DocType in case of Form or Report and page name in case of Page
   * `p2` is record name in case of DocType, criteria_name in case of Report
   
.. function:: nav_obj.show_last_open()

   Execute `Back` button

