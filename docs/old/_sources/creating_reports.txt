Creating Reports
================

Reports can be created and saved using the Report Builder. A report is saved in a record of type
"Search Criteria"

A Report is a SQL query that runs on the server side. The report builder builds the SQL query:

* Column selector
* Filters
* Sorting

Using the Search Criteria you can customize this query by adding

* more tables
* more conditions
* post-processing server side code
* styling the report with HTML by setting color etc.

Filters
-------

Filters appear in the report on fields where "In Filter" is checked in DocType

Saving a Report
---------------

Once you have selected the columns, you can save the report by the "Save" button on the toolbar. After saving
you can open the "Search Criteria" record by the "Advanced" button.

In the Search Criteria, you can customize various parts of the report by setting the fields

Seeing the Query
----------------

To see the query that has been generated, check the "Show Query" check box at the bottom of the "Result"
section.

Adding Joins
------------

If you want to join the selected table with another table, then you can add the table in the "Additional
Tables" field. Note all tables in the database are named as "tab" + DocType name

.. note::
  Whenever you add tables, conditions, use the standard way of naming the fields as `tablename`.`fieldname`

Over-riding the query
---------------------

You can completely customize a query using the Override field. Note, when you write a query it has to be in
the :term:`Standard Query` format.

Adding Scripts
--------------

Using scripts, you can:

#. Add / remove filters
#. Add columns (for example row totals)
#. Add rows (for example column totals)
#. Modify values
#. Get values from other tables etc
#. Add color to the values (from client side)
