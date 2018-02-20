# Getting Information From Another Document In Print Format

In a print format, you can get data from another document. For example in if you have a fields called `sales_order` in Sales Invoice, then you can get the sales order details using `frappe.get_doc`:

{% raw %}
	{% set sales_order_doc = frappe.get_doc("Sales Order", sales_order) %}

	{{ sales_order_doc.customer }}
{% endraw %}
