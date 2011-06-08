:mod:`db_schema` --- Database Schema Management Module
======================================================

.. module:: db_schema
   :synopsis: Database Schema Management Module

Syncs a database table to the `DocType` (metadata)
*Note* This module is only used internally

.. method:: updatedb(dt)

   Syncs a `DocType` to the table
   * creates if required
   * updates columns
   * updates indices
   
.. method:: getcoldef(ftype, length='')

   converts the user defined field types (ftype) to database fieldtypes
   example: `Data` becomes `varchar(180)`
   
   Default field lengths:
   
   * 180  - Data / Select / Link / Read Only / Password
   * 14,2 - Currency
   * 14,6 - Float
			
.. method:: updatecolumns(doctype)

   Updates columns from the `DocType` to the table
   
   * adds a column if new
   * changes the name if oldfieldname != fieldname
   * changes the type

.. method:: updateindex(doctype)

   Adds / removes indices from the given doctype table
   
.. method:: update_engine(doctype=None, engine='InnoDB')

   Not used: Updated the MySQL table engine

.. method:: create_table(dt)

   Creates a table for a new doctype
   
Standard fields of a record
---------------------------
   
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

