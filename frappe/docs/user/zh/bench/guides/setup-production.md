# 生产环境部署

你可以通过配置 Supervisor、Nginx 来部署生产环境。如果你想把生产环境恢复为开发环境，请参考[这些命令](https://github.com/frappe/bench/wiki/Stopping-Production-and-starting-Development)。

#### 自动部署生产环境
运行命令 `sudo bench setup production` 将自动完成生产环境部署。


#### 手工部署生产环境

Supervisor
----------

Supervisor 确保 Frappé 系统进程保持运行并在它发生崩溃后自动重新启动。你可以使用命令 `bench setup supervisor` 生成  Supervisor 所需的配置。该配置可参考`config/supervisor.conf` 文件。你可以将该文件复制或链接到 supervisor 配置目录并重新加载它以使其生效。 

例如,

```
bench setup supervisor
sudo ln -s `pwd`/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf
```

注意：对于 CentOS 7, 其扩展名应是 `ini`, 因此命令变成了：

```
bench setup supervisor
sudo ln -s `pwd`/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.ini #for CentOS 7 only
```

更新 supervisor 配置后需要重启 supervisor 管理的相关进程。要自动完成它，你需要使用命令 `sudo bench setup sudoers $(whoami)` 对 sudoers 进行配置。

Nginx
-----

Nginx 是一个 Web 服务器，我们用它来提供静态文件以及其他对 Frappe 请求的代理。你可以使用命令 `bench setup nginx` 生成  Supervisor 所需的配置。该配置可参考`config/nginx.conf` 文件。你可以将该文件复制或链接到 nginx 配置目录并重新加载它以使其生效。 

例如,

```
bench setup nginx
sudo ln -s `pwd`/config/nginx.conf /etc/nginx/conf.d/frappe-bench.conf
```

注意：如果有另一个端口配置为 80 的服务存在，在你更改配置后重新启动 Nginx 可能失败（多数情况下导致 Nginx 的欢迎页出现）。你需要禁用此配置。通常它们位于 `/etc/nginx/conf.d/default.conf` 和 `/etc/nginx/conf.d/default` 中。
