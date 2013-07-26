# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import unicode_literals
import webnotes

from webnotes.utils import getdate, cint, add_months, date_diff, add_days

weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

@webnotes.whitelist()
def get_events(start, end):
	roles = webnotes.get_roles()
	events = webnotes.conn.sql("""select name, subject, 
		starts_on, ends_on, owner, all_day, event_type, repeat_this_event, repeat_on,
		monday, tuesday, wednesday, thursday, friday, saturday, sunday
		from tabEvent where (
			(starts_on between '%(start)s' and '%(end)s')
			or (ends_on between '%(start)s' and '%(end)s')
		) or (
			starts_on < '%(start)s' and ifnull(repeat_this_event,0)=1 and
			ifnull(repeat_till, "3000-01-01 00:00:00") > '%(start)s'
		)
		and (event_type='Public' or owner='%(user)s'
		or exists(select * from `tabEvent User` where 
			`tabEvent User`.parent=tabEvent.name and person='%(user)s')
		or exists(select * from `tabEvent Role` where 
			`tabEvent Role`.parent=tabEvent.name 
			and `tabEvent Role`.role in ('%(roles)s')))
		order by starts_on""" % {
			"start": start,
			"end": end,
			"user": webnotes.session.user,
			"roles": "', '".join(roles)
		}, as_dict=1)
		
	# process recurring events
	start = start.split(" ")[0]
	end = end.split(" ")[0]
	add_events = []
	
	def add_event(e, date):
		new_event = e.copy()
		new_event.starts_on = date + " " + e.starts_on.split(" ")[1]
		new_event.ends_on = date + " " + e.ends_on.split(" ")[1]
		add_events.append(new_event)
	
	for e in events:
		if e.repeat_this_event:
			event_start, time_str = e.starts_on.split(" ")
			if e.repeat_on=="Every Year":
				start_year = cint(start.split("-")[0])
				end_year = cint(end.split("-")[0])
				event_start = "-".join(event_start.split("-")[1:])
				
				# repeat for all years in period
				for year in range(start_year, end_year+1):
					date = str(year) + "-" + event_start
					if date > start and date < end:
						add_event(e, date)
				events.remove(e)

			if e.repeat_on=="Every Month":
				date = start.split("-")[0] + "-" + start.split("-")[1] + "-" + event_start.split("-")[2]
				
				# last day of month issue, start from prev month!
				try:
					getdate(date)
				except ValueError:
					date = date.split("-")
					date = date[0] + "-" + str(cint(date[1]) - 1) + "-" + date[2]
					
				start_from = date
				for i in xrange(int(date_diff(end, start) / 30) + 3):
					if date >= start and date <= end and date >= event_start:
						add_event(e, date)
					date = add_months(start_from, i+1)
				events.remove(e)

			if e.repeat_on=="Every Week":
				weekday = getdate(event_start).weekday()
				# monday is 0
				start_weekday = getdate(start).weekday()
				
				# start from nearest weeday after last monday
				date = add_days(start, weekday - start_weekday)
				
				for cnt in xrange(int(date_diff(end, start) / 7) + 3):
					if date >= start and date <= end and date >= event_start:
						add_event(e, date)

					date = add_days(date, 7)
				events.remove(e)

			if e.repeat_on=="Every Day":				
				for cnt in xrange(date_diff(end, start) + 1):
					date = add_days(start, cnt)
					if date <= end and e[weekdays[getdate(date).weekday()]]:
						add_event(e, date)
				events.remove(e)

	return events + add_events