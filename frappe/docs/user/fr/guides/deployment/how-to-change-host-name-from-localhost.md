While using a virtual machine, links within emails will be point to your host, e.g. localhost, like **http://localhost/set-password** etc.

Frappe will automatically extract the host name from the incoming request, or from the `host_name` property from `site_config`. 

### bench set-config

To fix this, you can use **bench set-config** to set your public IP or domain name as the host name.

#### Example:

	bench --site mysite.com set-config host_name mysite.com

---

Or edit the `frappe-bench/sites/mysite.com/site_config.json` and add a `host_name` property.


<!-- markdown -->