# 手工设置

手工设置
--------------

安装必备组件，

* [Python 2.7](https://www.python.org/download/releases/2.7/)
* [MariaDB](https://mariadb.org/)
* [Redis](http://redis.io/topics/quickstart)
* [WKHTMLtoPDF with patched QT](http://wkhtmltopdf.org/downloads.html) (生成 pdf 需要)

[在 OSX 下安装必备组件](https://github.com/frappe/bench/wiki/Installing-Bench-Pre-requisites-on-MacOSX)

以*非 root 用户*安装 bench，

		git clone https://github.com/frappe/bench bench-repo
		sudo pip install -e bench-repo

提示：请不要删除上述命令将创建的 bench 目录


从现有安装迁移
------------------------------------

如果想从 ERPNext 版本 3 迁移，请参照[这里](https://github.com/frappe/bench/wiki/Migrating-from-ERPNext-version-3)的说明

如果想从老版本的 Bench 迁移，请参照[这里](https://github.com/frappe/bench/wiki/Migrating-from-old-bench)的说明


基本用法
===========

* 创建新的 Bench

	命令 init 将创建一个安装了 frappe 框架的 bench 目录。它将被设置为定期备份和每天一次的自动更新。

		bench init frappe-bench && cd frappe-bench

* 添加应用

	命令 get-app 获取并安装 frappe 应用。例如：
	
	- [erpnext](https://github.com/frappe/erpnext)
	- [erpnext_shopify](https://github.com/frappe/erpnext_shopify)
	- [paypal_integration](https://github.com/frappe/paypal_integration)
	
	bench get-app erpnext https://github.com/frappe/erpnext

* 添加站点

	Frappé 应用由 frappe 站点运行，您需要至少创建一个站点。命令 new-site 可以达到该目的：

		bench new-site site1.local

* 启动 Bench

	要启动 Bench，使用 `bench start` 命令

		bench start

	要登录 Frappé / ERPNext，打开你的浏览器输入 `localhost:8000`

	默认用户名为 "Administrator"，密码则是当你设置新站点时指定的密码。


配置 ERPNext
==================

要安装 ERPNext，只需运行：
```
bench install-app erpnext
```

现在你可以使用 `bench start` 启动或[设置生产用 Bench](setup-production.html)
