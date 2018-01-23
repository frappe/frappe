# 配置 HTTPS

### 获取必要的文件

你可以从受信任的证书颁发机构获得 SSL 证书或生成自己的证书。对于自签名证书，浏览器将显示一个 “该证书不受信任” 的警告。[这里是通过 Let's Encrypt 获取免费 SSL 证书的教程](lets-encrypt-ssl-setup.html)

这些必要的文件包括：

* 证书 (通常后缀名为 .crt)
* 解密的私钥

如果你有多个证书（初级和中级），你将需要将它们连接起来。例如，

	cat your_certificate.crt CA.crt >> certificate_bundle.crt

还要确保你的私钥不可读。一般来说，它只有 root 才能是所有者和可读

	chown root private.key
	chmod 600 private.key

### 将两个文件移动到适当的位置

	mkdir /etc/nginx/conf.d/ssl
	mv private.key /etc/nginx/conf.d/ssl/private.key
	mv certificate_bundle.crt /etc/nginx/conf.d/ssl/certificate_bundle.crt

### 设置 Nginx 配置

为你的站点设置证书和私钥的路径
	
	bench set-ssl-certificate site1.local /etc/nginx/conf.d/ssl/certificate_bundle.crt
	bench set-ssl-key site1.local /etc/nginx/conf.d/ssl/private.key

### 生成 Nginx 配置
	
	bench setup nginx

### 重启 Nginx
	
	sudo service nginx reload

或

	systemctl reload nginx # for CentOS 7 

现在你已完成了 SSL 的配置，所有 HTTP 通信都将重定向到 HTTPS