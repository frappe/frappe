Report Cookbook
===============

Standard patterns used to customize reports

Modify Report Filters (Client)
------------------------------

Filters can be modified declaring the customize_filters method::

  report.customize_filters = function() {
    this.hide_all_filters();

    // show these filters only
    this.filter_fields_dict['GL Entry'+FILTER_SEP +'From Posting Date'].df.filter_hide = 0;
    this.filter_fields_dict['GL Entry'+FILTER_SEP +'To Posting Date'].df.filter_hide = 0;
    this.filter_fields_dict['GL Entry'+FILTER_SEP +'Account'].df.filter_hide = 0;
  
    // add new filters
    this.add_filter({fieldname:'aging_based_on', label:'Aging Based On', fieldtype:'Select', options:NEWLINE+'Transaction Date'+NEWLINE+'Aging Date'+NEWLINE+'Due Date',ignore : 1, parent:'Receivable Voucher', report_default:'Aging Date'});  
    this.add_filter({fieldname:'range_1', label:'Range 1', fieldtype:'Data', ignore : 1, parent:'GL Entry'});

    // set default filters
    this.filter_fields_dict['GL Entry'+FILTER_SEP +'From Posting Date'].df['report_default']=sys_defaults.year_start_date;
    this.filter_fields_dict['GL Entry'+FILTER_SEP +'To Posting Date'].df['report_default']=dateutil.obj_to_str(new Date());
    this.filter_fields_dict['GL Entry'+FILTER_SEP +'Company'].df['report_default']=sys_defaults.company;
  }
  
Remove Paging for a Report (Client)
-----------------------------------

If you want the report to skip paging and show all records then you can define as follows::

  report.dt.set_no_limit(1);

Hide Column Picker (Client)
---------------------------

If you want the user to only view the set columns and hide the column picker set as follows::

  $dh(this.mytabs.tabs['Select Columns'])

Validate fitler values (Server)
-------------------------------

Check if user has set valid data for the filters. This code is in the Server Side::

  # Check mandatory filters
  #------------------------------

  if not filter_values.get('posting_date') or not filter_values.get('posting_date1'):
    msgprint("Please select From Posting Date and To Posting Date in 'Set Filters' section")
    raise Exception
  else:
    from_date = filter_values.get('posting_date')
    to_date = filter_values.get('posting_date1')


Append a column to the report (Server)
--------------------------------------

Column structure is defined in the colnames, coltypes, colwidths and coloptions lists. 
You can modify or append to its values::

  colnames.append('Total')
  coltypes.append('Currency')
  colwidths.append('200px')
  coloptions.append('')
  col_idx[d[0]] = len(colnames)-1

Add data to a column (Server)
-----------------------------

The result is set to the list "res". You can maniupate res on the server site, before it is sent
to the client

Values of columns can be found by label using the dictionary col_idx::

  for r in res:
    # customer cost center
    terr = sql("""select t1.territory from `tabCustomer` t1, `tabAccount` t2 
    	where t1.name = t2.master_name and t2.name = '%s'""" % r[col_idx['Account']])
    r.append(terr and terr[0][0] or '')

    # get due date
    due_date = sql("""select due_date from `tabReceivable Voucher` 
    	where name = '%s'""" % r[col_idx['Against Voucher']])
    r.append(due_date and cstr(due_date[0][0]) or '')
  
Append rows to the report (Server)
----------------------------------

This example adds an extra row to the data on the server side::

  # Append Extra rows to RES
  t_row = ['' for i in range(len(colnames))]
  t_row[col_idx['Voucher No']] = 'Total'
  t_row[col_idx['Opening Amt']] = total_opening_amt
  t_row[col_idx['Outstanding Amt']] = total_outstanding_amt
  out.append(t_row)