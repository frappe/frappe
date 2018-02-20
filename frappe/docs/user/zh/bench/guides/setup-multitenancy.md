# 多租户模式配置

假设你已经运行了你的第一个站点，并完成了[生产环境部署](setup-production.html)，这篇文章将展示如何托管你的第二个站点（或更多）。你的第一个站点自动设置为默认站点。你可以通过如下命令更改默认站点，

	bench use sitename

基于端口的多租户模式
-----------------------

你可以创建新的站点并运行在不同的端口上（第一个站点运行在 80 端口）。


* 关闭基于 DNS 的多租户模式 (一次即可)

  `bench config dns_multitenant off`

* 新增站点

  `bench new-site site2name`

* 设置端口

  `bench set-nginx-port site2name 82`

* 重新生成 Nginx 配置

  `bench setup nginx`

* 重新加载 Nginx 服务

  `sudo service nginx reload`


基于 DNS 的多租户模式
----------------------
将你的站点命名为主机名（hostname）即可。你的所有站点都将运行在相同的端口上并根据其主机名（hostname）自动选择。

基于DNS的多租户在做一个新的网站，请执行以下步骤。

* 开启基于 DNS 的多租户模式 (一次即可)

  `bench config dns_multitenant on`

* 新增站点

  `bench new-site site2name`

* 重新生成 Nginx 配置

  `bench setup nginx`

* 重新加载 Nginx 服务

  `sudo service nginx reload`
