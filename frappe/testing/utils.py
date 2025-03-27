import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


def debug_timer(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		start_time = time.monotonic()
		result = func(*args, **kwargs)
		end_time = time.monotonic()
		logger.debug(f" {func.__name__:<50}  ⌛{end_time - start_time:>6.3f} seconds")
		return result

	return wrapper
