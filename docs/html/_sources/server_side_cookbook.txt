Server Side Cookbook
====================

Standard Patterns for server side scripts

Create a name by using a prefix selected by the user
----------------------------------------------------

You can create a field "naming_series" of type Select and give Options. Then you can write the autoname function
as follows::

  # Autoname
  def autoname(self):
    self.doc.name = make_autoname(self.doc.naming_series+'.#####')



Stop duplicate entries in a child table based on a key
------------------------------------------------------

For example, your key is item_code. Call this method from the validate method::

  # Does not allow same item code to be entered twice
  def validate_for_items(self):
    check_list=[]
    for d in getlist(self.doclist,'quotation_details'):
      if d.item_code in check_list:
        msgprint("Oops! Item %s has been entered twice." % d.item_code)
        raise Exception
      else:
        check_list.append(cstr(d.item_code))
        


Add an event to the calendar
----------------------------

Add an event to the calendar on saving::

  # Add to Calendar
  def add_calendar_event(self):
    ev = Document('Event')
    ev.description = self.doc.description
    ev.event_date = self.doc.contact_date
    ev.event_hour = '10:00'
    ev.event_type = 'Private'
    ev.ref_type = 'Enquiry'
    ev.ref_name = self.doc.name
    ev.save(1)
    
    # invite users (Sales People) to the event
    user_lst.append(self.doc.owner)
    
    chk = sql("select t1.name from `tabProfile` t1, `tabSales Person` t2 where t2.email_id = t1.name and t2.name=%s",self.doc.contact_by)
    if chk:
      user_lst.append(chk[0][0])
    
    for d in user_lst:
      ch = addchild(ev, 'event_individuals', 'Event User', 0)
      ch.person = d
      ch.save(1)

  # on_udpate method
  def on_update(self):
    # Add to calendar
    if self.doc.contact_date and self.doc.contact_date_ref != self.doc.contact_date:
      if self.doc.contact_by:
        self.add_calendar_event()
      set(self.doc, 'contact_date_ref',self.doc.contact_date)
      


Send HTML Email based on certain condition
------------------------------------------

Email can be sent using the sendmail method. In this message, we send an email when the
quantity of a certain item falls below the minimum inventory level::

  def check_min_inventory_level(self):
    if self.doc.minimum_inventory_level:
      total_qty = sql("select sum(projected_qty) from tabBin where item_code = %s",self.doc.name)
      if flt(total_qty) < flt(self.doc.minimum_inventory_level):
        msgprint("Minimum inventory level for item %s is reached", self.doc.name)
        send_to = []
        send = sql("select t1.email from `tabProfile` t1,`tabUserRole` t2 where t2.role IN ('Material Master Manager','Purchase Manager') and t2.parent = t1.name") 
        for d in send:
          send_to.append(d[0])
        msg = '''Minimum Inventory Level Reached

        Item Code: %s
        Item Name: %s
        Minimum Inventory Level: %s
        Total Available Qty: %s

        ''' % (self.doc.item_code, self.doc.item_name, self.doc.minimum_inventory_level, total_qty)

	sendmail(send_to, sender='automail@webnotestech.com', subject='Minimum Inventory Level Reached', parts=[['text/plain', msg]])


