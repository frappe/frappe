# Copyright (c) 2017, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts


@nts.whitelist()
def get_leaderboard_config():
	leaderboard_config = nts._dict()
	leaderboard_hooks = nts.get_hooks("leaderboards")
	for hook in leaderboard_hooks:
		leaderboard_config.update(nts.get_attr(hook)())

	return leaderboard_config
