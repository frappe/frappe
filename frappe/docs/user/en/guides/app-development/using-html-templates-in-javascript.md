Often while building javascript interfaces, there is a need to render DOM as an HTML template. Frappe Framework uses John Resig's Microtemplate script to render HTML templates in the Desk application.

> Note 1: In Frappe we use the Jinja-like `{%` tags to embed code rather than the standard `<%`

> Note 2: Never use single quotes `'` inside the HTML template.

To render a template,

1. Create a template `html` file in your app. e.g. `address_list.html`
1. Add it to `build.json` for your app (you can include it in `frappe.min.js` or your own javascript file).
1. To render it in your app, use `frappe.render(frappe.templates.address_list, {[context]})`

#### Example Template:

From `erpnext/public/js/templates/address_list.js`


	<p><button class="btn btn-sm btn-default btn-address">
	    <i class="icon-plus"></i> New Address</button></p>
	{% for(var i=0, l=addr_list.length; i<l; i++) { %}
	    <hr>
	    <a href="#Form/Address/{%= addr_list[i].name %}" class="btn btn-sm btn-default pull-right">
	        {%= __("Edit") %}</a>
	    <h4>{%= addr_list[i].address_type %}</h4>
	    <div style="padding-left: 15px;">
	        <div>
        	    {% if(addr_list[i].is_primary_address) { %}<span class="label label-info">
	                {%= __("Primary") %}</span>{% } %}
	            {% if(addr_list[i].is_shipping_address) { %}<span class="label label-default">
        	        {%= __("Shipping") %}</span>{% } %}
	        </div>
	        <p style="margin-top: 5px;">{%= addr_list[i].display %}</p>
	    </div>
	{% } %}
	{% if(!addr_list.length) { %}
	<p class="text-muted">{%= __("No address added yet.") %}</p>
	{% } %}




<!-- markdown -->