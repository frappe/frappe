:mod:`doc` --- Document (ORM)
=============================

.. module:: doc
   :synopsis: Document (ORM) Module

.. function:: get(dt, dn=''):

   Returns a doclist containing the main record and all child records
   
Document object
---------------

.. class:: Document(doctype = '', name = '', fielddata = {})

   The `Document` class represents the basic Object-Relational Mapper (ORM). The object type is defined by
   `DocType` and the object ID is represented by `name`:: 
   
      Please note the anamoly in the Web Notes Framework that `ID` is always called as `name`

   If both `doctype` and `name` are specified in the constructor, then the object is loaded from the database.
   If only `doctype` is given, then the object is not loaded
   If `fielddata` is specfied, then the object is created from the given dictionary.
       
      **Note 1:**
      
         The getter and setter of the object are overloaded to map to the fields of the object that
         are loaded when it is instantiated.
       
         For example: doc.name will be the `name` field and doc.owner will be the `owner` field

      **Note 2 - Standard Fields:**
      
         * `name`: ID / primary key
         * `owner`: creator of the record
         * `creation`: datetime of creation
         * `modified`: datetime of last modification
         * `modified_by` : last updating user
         * `docstatus` : Status 0 - Saved, 1 - Submitted, 2- Cancelled
         * `parent` : if child (table) record, this represents the parent record
         * `parenttype` : type of parent record (if any)
         * `parentfield` : table fieldname of parent record (if any)
         * `idx` : Index (sequence) of the child record

   .. attribute:: fields
   
      Dictionary containing the properties of the record. This dictionary is mapped to the getter and setter
   
   .. method:: save(new=0, check_links=1, ignore_fields=0)
   
      Saves the current record in the database. If new = 1, creates a new instance of the record.
      Also clears temperory fields starting with `__`
      
      * if check_links is set, it validates all `Link` fields
      * if ignore_fields is sets, it does not throw an exception for any field that does not exist in the 
        database table
      		
   .. method:: clear_table(doclist, tablefield, save=0)

      Clears the child records from the given `doclist` for a particular `tablefield`

   .. method:: addchild(self, fieldname, childtype = '', local=0, doclist=None)
   
      Returns a child record of the give `childtype`.
      
      * if local is set, it does not save the record
      * if doclist is passed, it append the record to the doclist
   
Standard methods for API
------------------------
   
.. function:: addchild(parent, fieldname, childtype = '', local=0, doclist=None):

   Create a child record to the parent doc.
   
   Example::
   
     c = Document('Contact','ABC')
     d = addchild(c, 'contact_updates', 'Contact Update', local = 1)
     d.last_updated = 'Phone call'
     d.save(1)
   
.. function:: removechild(d, is_local = 0)

   Sets the docstatus of the object d to 2 (deleted) and appends an 'old_parent:' to the parent name
			
Naming
------

.. function:: make_autoname(key, doctype='')

   Creates an autoname from the given key:
   
   **Autoname rules:**
      
         * The key is separated by '.'
         * '####' represents a series. The string before this part becomes the prefix:
            Example: ABC.#### creates a series ABC0001, ABC0002 etc
         * 'MM' represents the current month
         * 'YY' and 'YYYY' represent the current year
   
   *Example:*
   
         * DE/./.YY./.MM./.##### will create a series like
           DE/09/01/0001 where 09 is the year, 01 is the month and 0001 is the series

Inheritance
-----------

.. class:: BaseDocType:
   
   The framework supports simple inheritance using the BaseDocType class.
   It creates the base object and saves it in the property `super`. The getter then tries to retrive the
   property from the `super` object if it exsits before retrieving it from the current record.
   
   
Example
-------

Open an existing Contact::

  c = Document('Contact', 'ABC')
  c.phone_number = '233-3432'
  c.save()

Create a new Contact::

  c = Document('Contact')
  c.name = 'XYZ'
  c.phone_number = '342-3423'
  c.email_id = 'xyz@foo.com'
  c.save(new = 1)
  