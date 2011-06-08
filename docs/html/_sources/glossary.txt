.. _glossary:

Glossary
========

.. glossary:: 

   DocType
      The basic building block of the Web Notes Framework. A DocType represents multiple things
      
      * A table in the database (if `is_single` is `False`)
         A table is named as `tab` + the name of the Doctype
         Example: The table of doctype Content would be `tabContent`
      * A class
      * A form
      * An agent to perform certain actions
   
      A `DocType` has :term:`Fields`, :term:`Permissions` and :term:`Code`

   Single Type
      A DocType with property `is_single` as True.
      
      * No table is created for such a DocType
      * All field values are stored in the table `tabSingles`
      * Mostly used to write Control objects

   Document
      A single record wrapped by an object-relational mapper.
      The document object's properties can be set or accessed using the simple object notation. For example `doc.owner`

   doclist
      A list of :term:`Document` records representing a single record (along with all its child records). The first
      element in the list `doclist[0]` is the main record, the rest, if any, are child records.
   
   Permissions
      Role-based permissions are maintained in the DocType. Permissions can also be set on individual fields.
      This is done by defining levels. The default level is 0 for all fields.
      
      Permissions can also be set based on certain properties of the user or the role and this is called `match`
      
      If a property is set in `match` column of the permission, then that permission will only apply if
      
      * The user / role has that property (as defined in User Defaults)
      * The corresponding DocType has that property
      * The value of the property is same, i.e. matches
      
      Example: if the match is on field `department`, then the permission will only apply if the user
      is of the same department as the transaction. This can be used to allow group wise access that cannot
      be fulfilled by roles.
         
   Page
      A Page represpents a simple Page in the application. A page has:
      
      * Static HTML content
      * Javascript code, event code
      * CSS
      
      Pages can be used to create any type of UI and workflows
      
   Testing Mode
      A global flag indicates if the system is in testing mode. 
      
      * When the Testing Mode is setup, a copy of all tables is made and stored as `test` + the DocType
      * All sql queries are scrubbed so that `tab` + DocType becomes `test` + DocType
      * Example: tabContact becomes testContact
      
      The `Testing Mode` is designed to be seamless to the developer and separate series are also mainted for
      records created in the testing mode.
      
   Error Console
      A Dialog box showing exceptions from the current request. Can be seen by click on Tools -> Error Console
      on the :term:`Web Notes Toolbar`
     
   Web Notes Toolbar
      A toolbar that is shown by default to the Administrator. To turn this off, set a default property
      `hide_webnotes_toolbar` = 1, or set it in the :term:`Control Panel`
     
   Control Panel
      A :term:`Single Type` containing global defaults. The can be accessed from the :term:`Web Notes Toolbar` by
      going to Options -> Control Panel when logged in as Administrator
     
   Report Builder
      This can be accessed from the :term:`Web Notes Toolbar`. The Report Builder provides a way to generate
      tabular reports from DocType. You can select the columns of the report as well as filter the report
      on columns that have the `in_filter` property set
      
   Search Criteria
      Saved settings of the `Report Builder`. This can be used for "one-click" reports. Scripting and other
      settings can also be done in the Search Criteria
      
   Locals
      A local dictionary (object) in the browser that maintains all records (or metadata) loaded from the server. The format is
      locals[`DocType`][`name`]. If an object is loaded in the current session, then it will be present in the
      locals object (dictionary)
      
   Standard Query
      A standardized way to write a SQL query for the query_builder. This will automatically add conditions
      relating to `match` permissions.
      
      For a standard query, 
      
      * All SQL keywords must be capitalized
      * All columms must be written as `tablename`.`colname`
      
      