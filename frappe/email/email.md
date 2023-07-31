# Email Architecture

This document describes the high-level architecture of how emails work in frappe.


### High Level View


Pulling/Sending:

![email-pull-flow](assets/images/email-pull-flow.png)

> NOTE: In the diagram, 2 types of workers are shown to execute from 2 different queues, however only 1 type of worker can also be used to do the same.

The same follows for email sending with the only difference in the job queued i.e: `queue.flush` .

The scheduler schedules/pushes the `email.pull`/`queue.flush` job into the default queue which is picked up by the (default) worker and upon execution enqueues `pull_from_email_account`/`send_mail` job into the short queue and the job is then picked up by the (short) worker and the email is pulled in/sent out of the system.


### Code Map

This section talks briefly about various important directories/files.

#### `doctype/email_queue`

Contains all logic pertaining to email sending. Every email to-be-sent is stored in `Email Queue` DocType.

#### `receive.py`

Contains all logic pertaining to email receiving. Every pulled email is stored in the `Communication` DocType.

If any error occurs in "handling" the inbound emails, they're stored in `Unhandled Email` Doctype.

#### `email_body.py`

Contains logic pertaining to creating the email body. We use python's email std lib for body generation.

The email message format/syntax is described in [RFC5322](https://datatracker.ietf.org/doc/html/rfc5322)
