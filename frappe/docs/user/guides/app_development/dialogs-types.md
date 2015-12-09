Frappe provide a group of standard dialogs that are very usefull while coding.

## Alert Dialog

![Alert](/files/show_alert.png)

Is helpfull for show a non-obstrutive message.

This dialog have 2 parameters `txt`that is the message and `seconds` that is the time that the message will be showed for the user, the standard is `3 seconds`.

### Example

	show_alert('Hi, do you have a new message', 5);

---

## Prompt Dialog

![Prompt](/files/promp_dialog.png)

Is helpful for ask a value for the user

This dialog have 4 parameters, they are:

- **fields:** a list with the fields objects
- **callback:** the function that manage the received values
- **title:** the title of the dialog
- **primary_label:** the label of the primary button

### Example

	frappe.prompt([
		{'fieldname': 'birth', 'fieldtype': 'Date', 'label': 'Birth Date', 'reqd': 1}  
	],
	function(values){
		show_alert(values, 5);
	},
	'Age verification',
	'Subscribe me'
	)

---
## Confirm Dialog

![Confirm](/files/confirm_dialog.png)

Usefull to get a confirmation from the user before do an action

This dialog have 3 arguments, they are:

- **mesage:**  The message content
- **onyes:** The callback on positive confirmation
- **oncancel:** The callback on negative confirmation

### Example

	frappe.confirm(
		'Are you sure to leave this page?',
		function(){
			window.close();
		},
		function(){
			show_alert('Thanks for continue here!')
		}
	)

---

## Message Print

![MSGPrint](/files/msgprint_dialog.png)

Is helpfull for show a informational dialog for the user;

This dialog have 2 arguments, they are:

- **message:** The message content, can be a HTML string too
- **title:** The title of the dialog

### Example

	msgprint("<b>Server Status</b>"
		+ "<hr>"
		+ "<ul>"
    			+ "<li><b>28%</b> Memory</li>"
    			+ "<li><b>12%</b> Processor</li>"
    			+ "<li><b>0.3%</b> Disk</li>"
		"</ul>", 'Server Info')

---

### Custom Dialog

![Class](/files/dialog_constructor.png)

Frappé provide too a `Class` that you can extend and build your own custom dialogs

`frappe.ui.Dialog`

### Example

	var d = new frappe.ui.Dialog({
		'fields': [
			{'fieldname': 'ht', 'fieldtype': 'HTML'},
			{'fieldname': 'today', 'fieldtype': 'Date', 'default': frappe.datetime.nowdate()}
		],
		primary_action: function(){
			d.hide();
			show_alert(d.get_values());
		}
	});
	d.fields_dict.ht.$wrapper.html('Hello World');
	d.show();




<!-- markdown -->