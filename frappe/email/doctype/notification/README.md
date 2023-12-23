# Notifications

The "Notification" DocType and its associated methods provide a comprehensive framework for managing and sending notifications within the Frappe application.

## Channels

The "channels" refer to the various means through which notifications can be sent.
Frappe has built-in support for the following channels for sending notifications:

- Email: Notifications can be sent via email to the specified recipients.
- Slack: Messages can be sent to Slack channels or users using the configured Slack webhook URL.
- System Notification: Notifications can be sent within the system as alerts or messages.
- SMS: Notifications can be sent as text messages to the specified mobile phone numbers.

## Handlers
 
Each channel is associated with a specific handler method for sending the notifications.
These are specified in the `hook.py` file and can be extended by downstream applications.
Refer to frappe's own `hook.py` for examples which implement the built in channels.

## Notification vs Communication

The _Communication_ DocType is responsible for logging and representing external communications such as emails, SMS, phone, chat, etc.
Although not limited to emails, with appropriate filters, it serves as Frappe's Inbox-like functionality.

One of its core functionalities is to log any such communication to external parties in the respective documents.
This allows the user can have a unified view about the state of an external conversation.

Therfore, a _Notification_ may also be a _Communication_ if it is intended to reach an external recipient.
Such a _Notification_ is generally classified as `communication_type = "Automated Message"` with the appropriate `communication_medium` (Email, Chat, SMS, ...).

## Notification vs System Notification

System Notifications are shown to the user via the desk's bell icon. The _Notification Log_ doctype serves as the centralized table for recording these system notifications and their state, such as if they already have been shown or acknowledge by the user.

"System Notification" can be configured as a channel in a _Notification_ in order to notify a user via the bell icon.

As such, it is **never** considered an external _Communication_.

