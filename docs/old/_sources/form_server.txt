:mod:`form` --- Form Module
===========================

.. module:: form
   :synopsis: Collection of methods that called by the Form widget from the client-side

.. method:: getdoc()

   Reads `doctype` and `name` from the incoming request (webnotes.form) and adds a `doclist` to the response 
   (webnotes.response)

.. method:: getdoctype()

   Reads `doctype` from the incoming request and returns a doclist of the DocType
   If `with_parent` is set in webnotes.form then, it returns with the first parent doctype incase of a child
   type (used in report builder)

.. method:: runserverobj()

   runserverobj method called by the `$c` (AJAX Call) function on client side
   
   * reads the incoming doclist
   * creates the object using :func:`code.get_server_obj`
   * executes the `method` using :func:`code.run_server_obj`

.. method:: savedocs()

   Saves the doc and all child records sent by the form when the "Save" button is clicked or `savedocs`
   is called from the client side.

   Also:
   * Checks for integrity - Latest record is being saved
   * Validates Links
   * Runs `validate`, `on_update`, `on_submit`, `on_cancel`

