:mod:`code` --- Code Execution Module
=====================================

.. module:: code
   :synopsis: Code Execution module

This is where all the plug-in code is executed. The standard method for DocTypes is declaration of a 
standardized `DocType` class that has the methods of any DocType. When an object is instantiated using the
`get_obj` method, it creates an instance of the `DocType` class of that particular DocType and sets the 
`doc` and `doclist` attributes that represent the fields (properties) of that record.

methods in following modules are imported for backward compatibility

	* webnotes.*
	* webnotes.utils.*
	* webnotes.model.doc.*
	* webnotes.model.doclist.*

Global Properties / Methods (generally) used in server side scripts
-------------------------------------------------------------------

.. data:: version

   "v170"

.. data:: NEWLINE

	"\\n" - used in plug in scripts

.. function:: set 

   Same as `webnotes.conn.set`
   Sets a value 
  
.. function:: sql(query, values=(), as_dict = 0, as_list = 0, allow_testing = 1)

   Same as `webnotes.conn.sql`

.. function:: get_value

   Sames as `webnotes.conn.get_value`

.. function:: convert_to_lists

	Same as `webnotes.conn.convert_to_lists`

Module Methods
--------------

.. function:: execute(code, doc=None, doclist=[])
   
   Execute the code, if doc is given, then return the instance of the `DocType` class created
	
.. function:: get_server_obj(doc, doclist = [], basedoctype = '')

   Returns the instantiated `DocType` object. Will also manage caching & compiling

.. function:: get_obj(dt = None, dn = None, doc=None, doclist=[], with_children = 0)

   Returns the instantiated `DocType` object. Here you can pass the DocType and name (ID) to get the object.
   If with_children is true, then all child records will be laoded and added in the doclist.
      
.. function:: run_server_obj(server_obj, method_name, arg=None)

   Executes a method (`method_name`) from the given object (`server_obj`)
   


