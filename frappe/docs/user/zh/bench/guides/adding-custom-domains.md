# 为站点添加自定义域名

你可以为站点添加 **多个自定义域名**，只需运行：

	bench setup add-domain [desired-domain]

在运行该命令时，将询问你要为哪个站点设置自定义域名。

你可以使用以下选项为自定义域名设置 SSL：

	--ssl-certificate [path-to-certificate]
	--ssl-certificate-key [path-to-certificate-key]

例如： 

	bench setup add-domain custom.erpnext.com --ssl-certificate /etc/letsencrypt/live/erpnext.cert --ssl-certificate-key /etc/letsencrypt/live/erpnext.key

域名配置保存在各站点自己的 site_config.json 配置文件里：

	 "domains": [
	  {
	   "ssl_certificate": "/etc/letsencrypt/live/erpnext.cert",
	   "domain": "erpnext.com",
	   "ssl_certificate_key": "/etc/letsencrypt/live/erpnext.key"
	  }
	 ],

**你需要通过运行 `bench setup nginx` 重新生成 Nginx 配置，并重新加载 Nginx 服务使你的自定义域名生效**