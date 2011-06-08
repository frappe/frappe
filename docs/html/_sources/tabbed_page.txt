Tabbed Page
===========

The TabbedPage class defines a simple tabbing system

TabbedPage Class
----------------

.. class:: TabbedPage(parent, only_labels)

   create a new TabbedPage in `parent`. If `only_labels` is set, do not create the page bodies only create
   labels
   
   .. attribute:: tabs
   
      A dictionary containing the tab labels. the key is the label name
   
   .. attribute:: cur_tab
   
      A reference to the current tab
      
   .. method:: add_tab(n, onshow)
   
      Will create a new Tab with label n. Call `onshow` when the tab is displayed. The tab has an
      element `tab_body` that is the Element in which the content of the tab is added.
      
      The tab can be accessed by `tabs` dictionary
      
   .. method:: disable_tab(n)
   
      Disable tab with label n
      
   .. method:: enable_tab(n)
   
      Enable tab with label n

Example
-------
      
Example using TabbedPage::

    var mytabs = new TabbedPage(parent);
    mytabs.add_tab('Tab 1', function() { refresh_list1(); })
    mytabs.add_tab('Tab 2', function() { refresh_list1(); })
    mytabs.add_tab('Tab 3', function() { refresh_list1(); })

    // add pages
    mytabs.tabs['Tab 1'].tab_body.innerHTML = "Some content in Tab 1"