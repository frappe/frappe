import runpy

from flow_harness import config


def test_redis_queue_settings_are_read_without_parsing_at_import(monkeypatch):
	settings = {
		"REDIS_MAX_PENDING": "1024",
		"REDIS_MAX_PENDING_PER_SITE": "invalid",
	}
	for name, value in settings.items():
		monkeypatch.setenv(f"FLOW_{name}", value)
	loaded = runpy.run_path(config.__file__)
	assert {name: loaded[name] for name in settings} == settings
