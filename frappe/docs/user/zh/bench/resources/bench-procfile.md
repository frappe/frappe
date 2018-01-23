# Bench Procfile 

在**开发模式**下 `bench start` 使用 [honcho](http://honcho.readthedocs.org) 管理多个流程。

### 过程

运行 Frappe 所需的相关过程是：

1. `bench start` - Web 服务
4. `redis_cache` 用于缓存 (通常)
5. `redis_queue` 用于管理后台执行单元队列
6. `redis_socketio` 作为来自后台执行单元的实时消息代理
7. `web` 用于 frappe Web 服务
7. `socketio` 用于实时消息
3. `schedule` 用于触发定期任务
3. `worker_*` 用于 redis 执行单元处理异步任务

或者，如果你在开发 Frappe，你可以添加 `bench watch` 自动创建桌面 JavaScript 应用。

### 例子

	redis_cache: redis-server config/redis_cache.conf
	redis_socketio: redis-server config/redis_socketio.conf
	redis_queue: redis-server config/redis_queue.conf
	web: bench serve --port 8000
	socketio: /usr/bin/node apps/frappe/socketio.js
	watch: bench watch
	schedule: bench schedule
	worker_short: bench worker --queue short
	worker_long: bench worker --queue long
	worker_default: bench worker --queue default
