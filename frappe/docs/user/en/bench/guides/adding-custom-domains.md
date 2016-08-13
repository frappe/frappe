# Adding Custom Domains to your Site

You can add **multiple custom domains** for your site, just run: 

	bench setup add-domain [desired-domain]

On running the command you will be asked for which site you want to set the custom domain for. 

You can also setup SSL for your custom domain by using the options: 

	--ssl-certificate [path-to-certificate]
	--ssl-certificate-key [path-to-certificate-key]

Example: 

	bench setup add-domain custom.erpnext.com --ssl-certificate /etc/letsencrypt/live/erpnext.cert --ssl-certificate-key /etc/letsencrypt/live/erpnext.key

Domain configuration is stored in the respective site's site_config.json

	 "domains": [
	  {
	   "ssl_certificate": "/etc/letsencrypt/live/erpnext.cert",
	   "domain": "erpnext.com",
	   "ssl_certificate_key": "/etc/letsencrypt/live/erpnext.key"
	  }
	 ],

**You will need to regenerate the nginx configuration by runnning `bench setup nginx` and reload the nginx service put your custom domain in effect**