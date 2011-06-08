.. _save_submit:

Save-Submit-Cancel Pattern
==========================

The framwork has an built-in pattern to "freeze" a record. This is typically useful in accounting type
of applications where a transaction cannot be altered once a subsequent transaction has been made and a 
"posting" is completed.

In the framework, a record has 3 stages as defined by the property "docstatus"

* 0 - Saved
* 1 - Submitted (frozen)
* 2 - Cancelled (or deleted)

After cancelling, you can also define an "Amend" permission. If the user is allowed to "Amend" a 
record, a new record is created against the cancelled record with a version number attached.
For example: Invoice IN003 becaomes IN003-1