import json
import os
from pathlib import Path
from tempfile import mkstemp

import frappe


def execute():
	"""The flow server's saved chats: the auto_approve flag became approval_mode."""
	for meta in Path(frappe.get_site_path("private", "flow", "sessions")).glob("*/*.meta.json"):
		config = json.loads(meta.read_text(encoding="utf-8"))
		if "auto_approve" not in config:
			continue
		legacy = config.pop("auto_approve")
		config.setdefault("approval_mode", "auto_approve" if legacy else "ask")
		# as the server writes it: owner-only, since it may hold a model key
		fd, tmp = mkstemp(prefix=f".{meta.name}.", dir=meta.parent)
		try:
			with os.fdopen(fd, "w", encoding="utf-8") as f:
				json.dump(config, f)
			os.replace(tmp, meta)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)
