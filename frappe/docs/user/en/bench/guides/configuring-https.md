# Configuring HTTPS

### Get the required files

You can get a SSL certificate from a trusted Certificate Authority or generate your own. For self signed certificates the browser will show a warning that the certificate is not trusted. [Here's a tutorial for using Let's Encrypt to get a free SSL Certificate](lets-encrypt-ssl-setup.html)

The files required are

* Certificate (usually with extension .crt)
* Decrypted private key

If you have multiple certificates (primary and intermediate), you will have to concatenate them. For example,

	cat your_certificate.crt CA.crt >> certificate_bundle.crt

Also make sure that your private key is not world readable. Generally, it is owned and readable only by root

	chown root private.key
	chmod 600 private.key

### Move the two files to an appropriate location

	mkdir /etc/nginx/conf.d/ssl
	mv private.key /etc/nginx/conf.d/ssl/private.key
	mv certificate_bundle.crt /etc/nginx/conf.d/ssl/certificate_bundle.crt

### Setup nginx config

Set the paths to the certificate and private key for your site
	
	bench set-ssl-certificate site1.local /etc/nginx/conf.d/ssl/certificate_bundle.crt
	bench set-ssl-key site1.local /etc/nginx/conf.d/ssl/private.key

### Generate nginx config
	
	bench setup nginx

### Reload nginx
	
	sudo service nginx reload

or

	systemctl reload nginx # for CentOS 7 

Now that you have configured SSL, all HTTP traffic will be redirected to HTTPS
