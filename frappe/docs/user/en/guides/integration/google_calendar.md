# Google Calendar Integration

Frappe provides an integration with Google Calendar in order for all users to synchronize their events.

## Setup

In order to allow a synchronization with Google Calendar you need to connect to your application in Google Cloud Platform and then create an account for each of your users:

1. Create a new project on Google Cloud Platform and generate new OAuth 2.0 credentials
2. Add `https://{yoursite}` to Authorized JavaScript origins
3. Add `https://{yoursite}?cmd=frappe.integrations.doctype.gcalendar_settings.gcalendar_settings.google_callback` as an authorized redirect URI
4. Add your Client ID and Client Secret in the Gcalendar application: in "Google Calendar>GCalendar Settings"

Once this step is successfully completed, each user can create its account in "Google Calendar>GCalendar Account"
They will be requested to authorize your Google application to access their calendar information and will then be redirected to a success page.


## Features

1. Creation of a new calendar in Google Calendar  
	- Each user can choose a dedicated name for its Google Calendar.

2. Events synchronization from ERPNext to GCalendar  
	- All events created in ERPNext are created in Google Calendar.
	- Recurring events are created as recurring events too.

	- Events modified in ERPNext are updated in Google Calendar.

	- Events deleted in ERPNext are deleted in Google Calendar.

3. Events synchronization from GCalendar to ERPNext  
	- Events created in Google Calendar are created in ERPNext.
	- Events updated in Google Calendar are updated in ERPNext.

The synchronization module follows ERPNext's authorization rule:

an event will be only synchronized if it is public or if the user his the owner.


## Limitations

Currently, if an instance of a recurring event is cancelled in Google Calendar, this change will not be reflected in ERPNext.
