# 为站点配置限额

Frappé v7 加入了对站点进行限额设置的支持。这些限额在站点文件夹内的 `site_config.json` 文件中设置，

	{
	 "db_name": "xxxxxxxxxx",
	 "db_password": "xxxxxxxxxxxx",
	 "limits": {
	  "emails": 1500,
	  "space": 0.157,
	  "expiry": "2016-07-25",
	  "users": 1
		}
	}

你可以运行以下命令设置限制：

	bench --site [sitename] set-limit [limit] [value]

你也可以同时设置多个限制，运行以下命令：
	
	bench --site [sitename] set-limits --limit [limit] [value] --limit [limit-2] [value-2]

 你可以设置的有效限制有: 

- **users** - 限制站点的最大用户数
- **emails** - 限制站每月邮件的发送数量上限
- **space** - 限制站点可以使用的最大存储空间(GB)
- **email_group** - 限制邮件群组中允许的最大成员数量
- **expiry** - 站点的到期日期(带括号的 YYYY-MM-DD 格式)

例如:

	bench --site site1.local set-limit users 5

你可以通过从工具栏/ AwesomeBar 打开 “使用信息” 页面查看使用情况。设置的限制会显示在该页面上。

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/usage_info.png">
