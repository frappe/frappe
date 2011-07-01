Server Side Scripts
===================

Introduction
------------

On the server-side, scripts are embedded in DocTypes. All scripts have to reside in classes in the DocTypes.

To add a server script, open a DocType you want to attach the script to and open the "Server Script" tab.

.. note::
   If you do not want the server script to be attached to any particular DocType, or call it from many
   DocTypes, you can create a "Single" DocType. Then using the get_obj method, you can call it from
   anywhere. More about it later.

Declaring a Class
-----------------
   
Server Side methods (functions) always reside in a "DocType" class, hence all your DocType classes will
be declared in the following manner::

   class DocType:
      
      # standard constructor
      def __init__(self, doc, doclist):
         self.doc = doc
         self.doclist = doclist

Let us see this constructor line by line

#. **class DocType** - This is the standard declaration of a class (for any DocType, the class will be labeled DocType)

#. **def __init__(self, doc, doclist):** - This is the constructor. The object will be constructed by the framework
   and the framework will supply the data record "doc" and a bundle of data-records including child records
   of this object in "doclist"
   
#. **self.doc = doc** - Set class property "doc" as the data object

#. **self.doclist = doclist** - Set the class property "doclist" as the list of child records

validate method
---------------

The validate method is called just before the user saves a record using the "Save" button. To stop the user
from saving, raise an Exception

Example::
  
  def validate(self):
      if self.doc.start_date > self.doc.finish_date:
         msgprint('Start date must be before finish date')
         raise Exception 

on_update, on_submit, on_cancel methods
---------------------------------------

These methods are called at various stages of saving a document, as defined in :doc:`save_submit`

The on_update method is called after the document values are saved in the database. If you raise an
Exception in any of these methods, the entire transaction will be rolled back.


Adding Child Records
--------------------

Child records can be added on the server side by the addchild method::

  addchild(parent, fieldname, childtype = '', local=0, doclist=None)

here is an example::
      
  c = Document('Contact','ABC')
  d = addchild(c, 'contact_updates', 'Contact Update', local = 1)
  d.last_updated = 'Phone call'
  d.save(1)

Debugging
---------

For de-bugging on the server side, you can

#. Print messages via msgprint(message)
#. Print error messages via errprint(message)

The full traceback of your error can be seen in **Tools -> Error Console**

