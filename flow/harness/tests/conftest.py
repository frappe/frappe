import os

# litellm's bundled model map; the live one changes upstream without notice
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
