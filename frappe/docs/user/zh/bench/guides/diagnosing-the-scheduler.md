# 诊断计划任务

<!-- markdown -->

如果你在计划任务中遇到延迟，或者似乎无法运行，可以运行几个命令来诊断问题。

### `bench doctor`

这将按顺序给出如下输出：
- 各站点计划任务状态
- 执行单元 (Workers) 数量
- 待处理任务


预期输出:

	Workers online: 0
	-----None Jobs-----

### `bench --site [site-name] show-pending-jobs`

这将按顺序给出如下输出：
- 队列
- 队列任务

预期输出:

	-----Pending Jobs-----


### `bench purge-jobs`

这将从所有队列中删除全部待处理的任务