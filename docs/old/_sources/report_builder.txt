Report Builder
==============

The Report Builder structure is as follows::

   +- Report Builder Container
      |
      +- Report Builder (DocType 1)
      |  |
      |  +- DataTable (Output grid)
      |
      +- Report Bulder (DocType 2)
      |
      ..
      ..

Search Criteria
---------------

Reports with selected columns and filters can be saved by clicking on the "Save" link on the top bar of
the Report Builder. The report is saved in a record called `Search Criteria`. Client-side and server-side
scripts can be plugged in by using the `Search Criteria`.

Customizing Filters
-------------------

Customizing of filters is done by declaring the `report.customize_filters` method in the client side of the
`Search Critiera`.

* Individual filters in the Report Builder can be accessed by the `filter_fields_dict`. The filter_fields_dict 
  returns a :class:`_f.Field` object. 
* Filters can be added by using the `add_filter` method
* The filters can be customized by setting properties on the `df` dictionary of the field object.

Custom properties of filter fields are

* `filter_hide` - Hide this standard filter
* `in_first_page` - Show this filter in the first page
* `report_default` - Set the value as the default for the filter
* `insert_before` - Insert this filter before the fieldname identified by this property
* `ignore` - Ignore this field while building the query
* `custom` - A property that indicates whether the filter is a custom filter (not a standard field)

Example::

   report.customize_filters = function() {
     // hide exiting filters
     this.hide_all_filters();

     // add a new filter
     this.add_filter({fieldname:'show_group_balance', label:'Show Group Balance', fieldtype:'Select', options:NEWLINE+'Yes'+NEWLINE+'No',ignore : 1, parent:'Account'});

     // add a "Company" filter
     this.filter_fields_dict['Account'+FILTER_SEP +'Company'].df.filter_hide = 0;
     
     // remove limts - show all records
     this.dt.set_no_limit(1);

     // hide tabs
     $dh(this.mytabs.tabs['Select Columns'])   
     
   }

Scrubbing / modifying data from the query
-----------------------------------------

The query can be scrubbed on the server side in Python before it. The result data is available as a list-in-a-list
`res`. The output can be modified by updating `res` or declaring a new list-in-a-list `out`

Standard lists, dictionary that can be updated

* `col_idx` - Index of columns by label
* `colwidths` - list of column widths
* `colnames` - list of column names
* `coltypes` - list of column types
* `colwidths` - list of column `options`
* `filter_values` - dictionary containing values of all filters

Example - adding a column::

   colnames.append('Total')
   coltypes.append('Currency')
   colwidths.append('120px')
   coloptions.append('')
   
   # set the index
   col_idx[c[0]] = len(colnames)-1

Example - adding the column data::

   sum = 0
   for r in res:
     # get the total as sum of 2 columns
     t = r[col_idx['Val 1']] + r[col_idx['Val 2']]
     sum += t
     
     # add it to the record
     r.push(t)

Example - getting value from a filter::

   if filter_values.get('Show sum')=='Yes':
   
     res.append(['','','', sum])

Adding style to the result
--------------------------

Style can be set on a row by declaring the `beforerowprint` method in the Client Script of the `Search Criteria`
Example::

   // Example 1: set foreground 
   report.beforerowprint = function(row){ 
     if(row.data[‘Amount’] > 20000) { 
       row.style.color = ‘GREEN’; 
     } 
   } 

   // Example 2: set background 
   report.beforerowprint = function(row){ 
     if(row.data[‘Amount’] < 1000) { 
       row.style.backgroundColor = ‘#FDD’; 
     } 
   }

Generating a query by script from client side
---------------------------------------------

A query can be generated from a script from the client side like in Listing by declaring the `get_query` method.
Note: Do not put ORDER BY and LIMIT as they would be appended by the Report Builder. There are 2 useful lists

 * report.selected_fields - list of selected fields in `Table_Name`.`field_name` format
 * report.filter_vals - dictionary of filter keys and values

Example::

   report.get_query = function() {
   	 var query = 'SELECT ' + report.selected_fields.join(', ') +  'FROM `tab..` WHERE ...';
   	 return query;
   }


Report Builder API
------------------

.. data:: _r

   Namespace for all objects related to Report Builder

Report Builder Container
------------------------


The Report Builder Container is the object that contains ReportBuilder objects for each DocType. This object
is managed automatically by the Framework

.. class:: _r.ReportBuilderContainer()

   .. data:: rb_dict
   
      Dictionary of all ReportBuilders. Key is the `DocType`

Report Builder Class
--------------------

.. class:: _r.ReportBuilder

   .. data:: large_report
   
      Flag indicating a report with many records as output. This will force the user to use "Export" only
      
   .. data:: filter_fields
   
      List of all filter fields
      
   .. data:: filter_fields_dict
   
      Dictionary of all filter fields. The key of this dictionary is the doctype + `FILTER_SEP` + label
      
   .. data:: dt
   
      Reference to the :class:`_r.Datatable` object of the Report Builder
      
   .. data:: mytabs
   
      `TabbedPage` object representing the tabs of the Report Builder. This can be used to hide / show
      tabs from the Client Script in the report like::
      
             $dh(this.mytabs.tabs['Select Columns'])   
      
   .. function:: customize_filters(report)
   
      The method is called when a new report or Search Criteria is loaded. The method (if exists)
      is usually used to customize filters as per the user requirments.
      
   .. function:: hide_all_filters()
   
      Will set the `df`.`filter_hide` property and hide all filters
      
   .. function:: set_column(doctype, label, value)
   
      Select / unselect a column. `value` must be 0 or 1
      
   .. function:: set_filter(doctype, label, value)
   
      Set the value of a filter
      
   .. function:: add_filter(f)
   
      Add a filter in the by specifying the field properties in a dictionary.
      
   .. function:: run()
   
      Execute the report

Datatable Class
---------------

.. class:: _r.Datatable(html_fieldname, dt, repname, hide_toolbar)

   The datatable class represents a grid object to show the results with paging etc

   .. function:: add_sort_option(label, value)
   
      Add a new field for sorting selection - value is the tablename.fieldname for the "ORDER BY" clause::
      
         report.dt.add_sort_option('ID','`tabMyDT`.`name`');

   .. function:: set_sort_option_disabled(label, disabled)
   
      Will enable / disable sort option by label. To disable, pass disabled = 1 or to enable pass disabled = 0
   
   .. attribute:: query
   
      Query to be executed (the paging using `LIMIT` & sorting is managed by the datatable)

   .. attribute:: page_len
   
      Length of a page (default 50)
   
   .. method:: set_no_limit(value)
   
      Run the query without adding limits if value = 1, (if value=0) run as standard, with limits
   
   .. method:: run
   
      Execute the query
      