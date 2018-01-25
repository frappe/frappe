# Script Report

You can create tabulated reports using server side scripts by creating a new Report.

> Note: You will need Administrator Permissions for this.

Since these reports give you unrestricted access via Python scripts, they can only be created by Administrators. The script part of the report becomes a part of the repository of the application. If you have not created an app, [read this](https://frappe.io/docs/user/en/guides/app-development/).

> Note: You must be in [Developer Mode](https://frappe.io/docs/user/en/guides/app-development/how-enable-developer-mode-in-frappe) to do this

### 1. Create a new Report

<img class="screenshot" alt="Script Report" src="/docs/assets/img/script-report.png">

1. Set Report Type as "Script Report"
1. Set "Is Standard" as "Yes"
1. Select the Module in which you want to add this report
1. In the module folder (for example if it is Accounts in ERPnext the folder will be `erpnext/accounts/report/[report-name]`) you will see that templates for the report files will be created.
1. In the `.js` file, you can set filters for the reports
1. In the `.py` file, you can write the script that will generate the report

### 2. Add Filters

You can add filters in the `.js`. See an example below:

	frappe.query_reports["Accounts Receivable"] = {
		"filters": [
			{
				"fieldname":"company",
				"label": __("Company"),
				"fieldtype": "Link",
				"options": "Company",
				"default": frappe.defaults.get_user_default("company")
			},
		]
	}

1. These properties are the same as you would set in a DocField in a DocType

### 3. Add the Script

In the `.py` file you can add the script for generating the report.

1. In the `execute` method, two lists `columns` and `data` are returned
2. Columns must be a list of labels in the same format as query report. **[Label]:[Field Type]/[Options]:[Width]**. For example `Item:Link/Item:150`
3. You can use all server side modules to build your report.
4. For example see existing reports. ([Balance Sheet](https://github.com/frappe/erpnext/blob/develop/erpnext/accounts/report/balance_sheet/balance_sheet.py))

### 4. Commit and Push the app

Don't forget to commit and push your app.
