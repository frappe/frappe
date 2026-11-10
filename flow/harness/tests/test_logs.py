"""Terminal logging for the serving daemon: format and level routing."""

import logging
import re

from flow_harness.server.logs import _TerminalFormatter, setup_terminal_logging


def _record(level: int, msg: str, args: tuple = ()) -> logging.LogRecord:
	return logging.LogRecord("test", level, "", 0, msg, args, None)


def test_formatter_stamps_time_and_names_only_bad_levels():
	fmt = _TerminalFormatter()
	line = fmt.format(_record(logging.INFO, '%s - "%s %s" %d', ("127.0.0.1", "GET", "/sessions", 200)))
	assert re.search(r"\d{2}:\d{2}:\d{2}", line)
	assert '127.0.0.1 - "GET /sessions" 200' in line
	assert "info" not in line
	assert "warning" in fmt.format(_record(logging.WARNING, "careful"))
	plain = _TerminalFormatter(color=False).format(_record(logging.WARNING, "careful"))
	assert "\033" not in plain


def test_setup_routes_access_lines_and_quiets_libraries():
	root = logging.getLogger()
	saved = (root.level, root.handlers[:])
	saved_levels = {name: logging.getLogger(name).level for name in ("uvicorn.access", "LiteLLM")}
	try:
		setup_terminal_logging()
		assert root.level == logging.WARNING
		assert isinstance(root.handlers[0].formatter, _TerminalFormatter)
		assert logging.getLogger("uvicorn.access").getEffectiveLevel() == logging.INFO
		assert logging.getLogger("LiteLLM").getEffectiveLevel() == logging.WARNING
	finally:
		root.handlers[:] = saved[1]
		root.setLevel(saved[0])
		for name, level in saved_levels.items():
			logging.getLogger(name).setLevel(level)
