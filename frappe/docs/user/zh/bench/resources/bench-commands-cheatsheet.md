# Bench 命令列表

### 常用

* `bench --version` - 显示 bench 版本
* `bench src` - 显示 bench 仓库目录
* `bench --help` - 显示所有命令和帮助
* `bench [command] --help` - 显示指定命令的帮助
* `bench init [bench-name]` - 创建新的工作台(bench) (在 home 目录下运行)
* `bench --site [site-name] COMMAND` - 指定命令应用的站点
* `bench update` - 从 bench 仓库和其他所有应用获取更新，应用补丁，重建 JS、CSS，然后执行迁移操作
  * `--pull`                获取所有应用的更新
  * `--patch`               执行所有站点的迁移
  * `--build`               重建 JS、CSS
  * `--bench`               更新 bench
  * `--requirements`        更新依赖
  * `--restart-supervisor`  更新后重启 supervisor 进程
  * `--upgrade`             进行主版本升级 ( 如 ERPNext 6 -> 7)
  * `--no-backup`           更新前不进行备份
* `bench restart` 重启所有 bench 服务 
* `bench backup` 备份 
* `bench backup-all-sites` 备份所有站点
  * `--with-files` 备份站点及其文件
* `bench restore` 恢复
  * `--with-private-files` 恢复站点及私有文件 (tar 文件路径)
  * `--with-public-files` 恢复站点及公共文件 (tar 文件路径)
* `bench migrate` 读取 JSON 文件并对数据库进行相应的更改

### 配置
* `bench config` - 更改 bench 配置
  * `auto_update [on/off]`          启用/禁用 bench 自动更新
  * `dns_multitenant [on/off]`      启用/禁用 DNS 多租户模式
  * `http_timeout`                  设置 http 超时时间
  * `restart_supervisor_on_update`  启用/禁用 更新时自动重启 supervisor
  * `serve_default_site`            配置 Nginx 默认站点
  * `update_bench_on_update`        启用/禁用 bench 同步更新
* `bench setup` - 设置组件
  * `auto-update`  为 bench 自动更新增加 cronjob 任务
  * `backups    `  为 bench 备份增加 cronjob 任务
  * `config     `  重写或生成 config.json
  * `env        `  生成 bench virtualenv 环境
  * `nginx      `  生成 nginx 配置文件
  * `procfile   `  设置 bench 启动过程文件(Procfile)
  * `production `  设置 bench 为生产环境
  * `redis      `  生成 redis 缓存配置文件
  * `socketio   `  设置 socketio 服务所需的 Node 依赖环境
  * `sudoers    `  增加命令到 sudoers 列表...
  * `supervisor `  生成 supervisor 配置文件
  * `add-domain `  增加站点自定义域名
  * `firewall `    设置防火墙并屏蔽除 22、80、443 之外的所有端口
  * `ssh-port `    更改 SSH 默认连接端口

### 开发

* `bench new-app [app-name]` 创建一个新的应用
* `bench get-app [repo-link]` - 从 git 仓库下载并安装一个应用
* `bench install-app [app-name]` 安装已有的应用
* `bench remove-from-installed-apps [app-name]` 从应用列表中移除应用
* `bench uninstall-app [app-name]` 删除应用及与该应用相关的一切 (须确保 Bench 在运行)
* `bench remove-app [app-name]` 从 bench 中彻底删除应用
* `bench --site [sitename] --force reinstall ` 全新数据库重新安装 (小心：将清除老的数据库) 
* `bench new-site [sitename]` - 创建一个新的站点
  * `--db-name`                数据库名称
  * `--mariadb-root-username`  MariaDB 数据库 root 用户名
  * `--mariadb-root-password`  MariaDB 数据库 root 密码
  * `--admin-password`         新站点的管理员密码
  * `--verbose`                显示详细信息
  * `--force`                  强制恢复 (如果站点已经存在)
  * `--source_sql`             使用 SQL 文件初始化数据库
  * `--install-app`            站点安装后安装应用
* `bench use [site]` 设置默认站点
* `bench drop-site` 从磁盘及数据库中完全移除站点
  * `--root-login` 
  * `--root-password`
* `bench set-config [key] [value]`   为站点配置文件增加键值对
* `bench console`   打开 bench venv 下的 IPython 终端
* `bench execute`   执行任何应用内的方法
  * 例如 : `bench execute frappe.utils.scheduler.enqueue_scheduler_events`
* `bench mysql`  打开 SQL 终端 
* `bench run-tests`  运行测试
  * `--app` 应用名称
  * `--doctype` 用于测试的 DocType
  * `--test` 具体测试
  * `--module` 运行具有测试的特定模块
  * `--profile` 运行具有测试的 Python 过程文件
* `bench disable-production`  禁用生产环境

### 计划任务

* `bench enable-scheduler` - 启用运行计划任务
* `bench doctor` - 显示有关后台执行单元的诊断信息
* `bench show-pending-jobs`- 显示未完成任务
* `bench purge-jobs` - 销毁所有未完成任务

