# 通过 Let's Encrypt 配置 HTTPS

## 必备条件

1. 你需要有 DNS 多租户 (Multitenant) 设置
2. 你的网站应可通过有效的域名访问
3. 你需要服务器的 root 权限

**注意 : Let's Encrypt 证书将每三个月到期**

## 使用 Bench 命令

运行: 

    sudo -H bench setup lets-encrypt [site-name]

您将碰到几个提示，请做出相应地回应。该命令还会向用户的 crontab 添加一个任务，每月尝试更新证书。

### 自定义域名

你还可以为[自定义域名](adding-custom-domains.html)设置 Let's Encrypt。使用 `--custom-domain` 选项即可

    sudo -H bench setup lets-encrypt [site-name] --custom-domain [custom-domain] 

### 刷新证书

你可以使用以下命令手工刷新证书：

    sudo bench renew-lets-encrypt

<hr>

## 手工方式

### 下载适当的 Certbot-auto 脚本到 /opt 目录中

    https://certbot.eff.org/

### 停止 nginx 服务

    $ sudo service nginx stop

### 运行 Certbot

    $ ./opt/certbot-auto certonly --standalone

在 letsencrypt 初始化后，将提示你输入一些信息。取决于你之前是否使用了 Let's Encrypt，这个提示可能会有所不同，但我们会第一时间指导你完成。

在提示中，输入用于通知、以及恢复丢失密钥的电子邮件地址：

![](https://assets.digitalocean.com/articles/letsencrypt/le-email.png)

你必须同意 Let's Encrypt 的订阅协议，选择同意：
![](https://assets.digitalocean.com/articles/letsencrypt/le-agreement.png)

然后输入你的域名。注意，如果你希望把一个证书用到多个域名上 (例如 example.com、www.example.com) ，确保像如下那样全部包含它们：

![](https://assets.digitalocean.com/articles/letsencrypt/le-domain.png)

### 证书文件

获得证书后，你将拥有以下 PEM 编码的文件：

* **cert.pem**: 你的域名证书
* **chain.pem**: Let's Encrypt 链证书
* **fullchain.pem**: 合并的 cert.pem 和 chain.pem
* **privkey.pem**: 你的证书私钥


这些证书文件保存在 `/etc/letsencrypt/live/example.com` 文件夹

### 为你的站点配置证书

转到你的 erpnext 站点 site_config.json

    $ cd frappe-bench/sites/{{site_name}}

添加以下两行到你的 site_config.json 文件中

    "ssl_certificate": "/etc/letsencrypt/live/example.com/fullchain.pem",
    "ssl_certificate_key": "/etc/letsencrypt/live/example.com/privkey.pem"


重新生成 Nginx 配置

    $ bench setup nginx

重启 Nginx 服务

    $ sudo service nginx restart

---

### 自动更新 (实验功能)

以 root 或拥有 superuser 权限的用户身份登录，运行 `crontab -e` 并输入:

    # 每月第一个周一刷新 letsencrypt 证书，如果执行完成后将收到邮件提示
    MAILTO="mail@example.com"
    0 0 1-7 * * [ "$(date '+\%a')" = "Mon" ] && sudo service nginx stop && /opt/certbot-auto renew && sudo service nginx start
