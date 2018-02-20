# 后台服务

外部服务
-----------------

	* MariaDB (Frappe 数据库)
	* Redis (Frappe 后台执行单元(Workers)和缓存查询)
	* nginx (用于生产环境部署)
	* supervisor (用于生产环境部署)

Frappé 进程
----------------

* WSGI 服务

	* 该 WSGI 服务负责相应对 frappe 的 HTTP 请求。在开发场景下 (`bench serve` 或 `bench start`) 为 Werkzeug WSGI 服务，生产场景下则使用 gunicorn (由 supervisor 自动配置)。

* Redis 执行单元(Workers)进程

	* 该 Celery 执行单元进程在 Frappé 系统里运行后台任务。当 supervisor 配置为生产环境时，这些进程在运行 `bench start` 时会自动启动。

* 计划任务进程

	* 计划任务进程在 Frappé 系统里运行规划的任务。当 supervisor 配置为生产环境时，该进程在运行 `bench start` 时会自动启动。