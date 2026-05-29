import logging

import frappe
import litellm
from frappe import _

from studio.ai.block_codec import BlockCodec
from studio.ai.models import ModelRegistry
from studio.ai.session import AISession
from studio.utils import has_page_write_perm

litellm.drop_params = True
logger = frappe.logger("studio.ai")
logger.setLevel(logging.INFO)

TASK_PARAMS = {
	"simple": {"max_tokens": 1000, "temperature": 0.5},
	"complex": {"max_tokens": 40000, "temperature": 0.7},
}

COMPONENT_CATALOG = """AVAILABLE COMPONENTS:
LAYOUT:
- container: layout wrapper (renders as a div). No componentProps. Use baseStyles: display, flexDirection, gap, padding, width, height, flexWrap, alignItems, justifyContent, flexShrink, flex, etc.

TEXT & DISPLAY:
- TextBlock: {text: "string", tag: "p|h1|h2|h3|h4|h5|h6|span", fontSize: "text-2xs(11px)|text-xs(12px)|text-sm(13px)|text-base(14px)|text-lg(16px)|text-xl(18px)|text-2xl(20px)|text-3xl(24px)|text-p-2xs|text-p-xs|text-p-sm|text-p-base|text-p-lg|text-p-xl|text-p-2xl|text-p-3xl"}
  # text-* = tight line-height (UI labels, headings); text-p-* = relaxed line-height (body copy, descriptions)
- Badge: {variant: "subtle|solid|outline", theme: "green|red|orange|blue|gray", size: "sm|md|lg", label: "string"}
- Avatar: {shape: "circle|square", size: "xs|sm|md|lg|xl|2xl|3xl", label: "initials", image: "url"}
- Progress: {value: 0-100, size: "sm|md|lg", label: "string"}
- Alert: {title: "string", description: "string", theme: "yellow|red|green|blue"}
- ErrorMessage: {message: "string"}
- FeatherIcon: {name: "feather-icon-name", class: "h-5 w-5"}
- ImageView: {image: "url", size: "xs|sm|md|lg|xl"}
- Divider: (no props)
- Tooltip: {text: "string"}
- HTML: {html: "<p>raw html</p>"}

INPUTS:
- TextInput: {placeholder: "string"}
- Textarea: {placeholder: "string"}
- FormControl: {type: "text|email|number|select|date|autocomplete|password", label: "string", placeholder: "string"}
- Select: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Checkbox: {label: "string", checked: true|false}
- Switch: {label: "string", description: "string", modelValue: true|false}
- DatePicker: {placeholder: "string"}
- TimePicker: {placeholder: "string"}
- DateTimePicker: {placeholder: "string"}
- MultiSelect: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Rating: {label: "string"}
- FileUploader: {label: "string", fileTypes: "['image/*']"}
- TextEditor: {modelValue: "string", editable: true, fixedMenu: true}

ACTIONS:
- Button: {label: "string", variant: "solid|subtle|outline|ghost", size: "sm|md|lg|xl|2xl", theme: "gray (DEFAULT — omit unless red/green/blue is semantically required)"}
- Dropdown: {options: [{label: "string", icon: "feather-icon"}], button: {label: "string"}}

NAVIGATION:
- Breadcrumbs: {items: [{label: "string", route: "string"}]}
- Tabs: {tabs: [{label: "string"}]}
- TabButtons: {buttons: [{label: "string", value: "string"}]}
- Sidebar: {header: {title: "string", subtitle: "string"}, sections: [{label: "string", items: [{label: "string", icon: "{{ getIcon('icon-name') }}", to: "string"}]}]}
  # icon-name must be a valid kebab-case lucide icon from https://lucide.dev/icons

DATA DISPLAY:
- ListView: {columns: [{label: "string", key: "string", width: number}], rows: [{key: value}], rowKey: "string"}
- NumberChart: {config: {title: "string", value: number, prefix: "string", delta: number}}
- AxisChart: {config: {data: [{xKey: val, yKey: val}], xAxis: {key: "string", type: "time|category"}, yAxis: {title: "string"}, series: [{name: "string", type: "bar|line"}]}}
- DonutChart: {config: {data: [{cat: val, val: number}], categoryColumn: "string", valueColumn: "string"}}
- Filter: {doctype: "string", filters: {}}
- Link: {doctype: "string"}
- Tree: {nodeKey: "string", node: {name: "string", label: "string", children: []}}
- Repeater: (no props — repeats child template over data)
- Calendar: {config: {defaultMode: "Month"}, events: []}

AUTOCOMPLETE:
- Autocomplete: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Combobox: {placeholder: "string", options: [{group: "string", options: [{label, value}]}]}
"""

STYLING_RULES = """COMPONENT STYLING RULES:
STYLE PROPERTY ROUTING — use the correct key:
- `style:` (panel-editable) — use ONLY these properties:
  Layout: display, flexDirection, justifyContent, alignItems, alignContent, alignSelf, flexWrap, flex, flexGrow, flexShrink, flexBasis, gap, rowGap, columnGap, overflowX, overflowY
  Grid: gridTemplateColumns, gridTemplateRows, gridColumn, gridRow
  Dimension: width, minWidth, maxWidth, height, minHeight, maxHeight
  Position: position, top, right, bottom, left, zIndex
  Spacing: margin, padding (and per-side: marginTop, marginRight, marginBottom, marginLeft, paddingTop, paddingRight, paddingBottom, paddingLeft)
  Typography: fontWeight, lineHeight, color, letterSpacing, textTransform, textAlign
  Visual: backgroundColor, borderColor, borderWidth, borderStyle, borderRadius, boxShadow, cursor
- `rstyle:` (raw styles) — for ALL other CSS properties not listed above: opacity, objectFit, objectPosition, whiteSpace, textOverflow, textDecoration, fontStyle, fontFamily, transform, transition, animation, wordBreak, overflowWrap, etc. Keep rstyle minimal — only include when genuinely needed.
- `mstyle:` (mobile styles) and `tstyle:` (tablet styles) — same properties as `style`, but for mobile and tablet breakpoints. Only include properties that need to change on mobile/tablet — do not duplicate the entire style object.
- Use %, rem for responsive widths. Top-level sections MUST be 100% width

CSS VARIABLE RULES:
- Always use CSS variables. Avoid raw hex colors/values.
  - backgroundColor: var(--surface-white) | var(--surface-gray-1..7) | var(--surface-cards) | var(--surface-red-1) | var(--surface-green-1) | var(--surface-amber-1) | var(--surface-blue-1)
  - color (text): var(--ink-white) | var(--ink-gray-1..9)
  - borderColor: var(--outline-white) | var(--outline-gray-1..5) | var(--outline-red-1..3) | var(--outline-green-1..2) | var(--outline-amber-1..2) | var(--outline-blue-1) | var(--outline-orange-1)
  - borderRadius: "0px" (none) | "0.25rem" (sm) | "0.5rem" (DEFAULT) | "0.625rem" (md) | "0.75rem" (lg) | "1rem" (xl) | "1.25rem" (2xl) | "9999px" (full)
- borderRadius — apply borderRadius (0.5rem by default) on cards, panels, containers by default, but NOT on full-width sections that span the entire viewport width.
- NEVER use the `border` shorthand property or per-side border properties: borderTopColor, borderTopWidth, borderTopStyle, borderLeftColor, borderLeftWidth, borderLeftStyle, borderRightColor, borderRightWidth, borderRightStyle, borderBottomColor, borderBottomWidth, borderBottomStyle — these are NOT in the style panel
- For full borders: borderColor, borderWidth (e.g. "1px"), borderStyle — always set all three together
- For one-sided borders: use CSS shorthand values — e.g. top-only: borderWidth: "4px 0px 0px 0px", borderColor: "var(--outline-blue-1)", borderStyle: "solid"
- Button: use size prop ("sm"|"md"|"lg"|"xl"|"2xl") for sizing — DO NOT set height in style. Keep `theme` gray or default unless prompted. Only use colored themes (blue, red, green) when semantically meaningful: destructive actions → red, success/confirmed → green.
- Avoid applying visual style (color, backgroundColor, borderColor, fontSize) to frappe-ui components — their props handle this. Only use style on `container` components for layout (width, flex, margin, etc.)."""

OUTPUT_FORMAT_RULES = """YAML STRING QUOTING (critical — unquoted special characters break parsing):
- Critical: Return ONLY a valid and compact YAML object. No markdown, no explanations.
- Always double-quote strings that contain any of: apostrophe/single-quote, `?`, `#`, `&`, `:`, `[`, `]`, `{`, `}`
- URLs must always be double-quoted: `image: "https://example.com/img?id=1"` NOT `image: https://example.com/img?id=1`
- Text with apostrophes must use double quotes: `text: "I'm a designer"` NOT `text: 'I'm a designer'`
- Long text values (bio, description, body copy) must use block scalar style instead of inline: `text: |` on its own line, then the text indented — never inline in a flow mapping"""

SYSTEM_PROMPT = f"""You are an expert UI developer specializing in creating responsive app pages for Frappe Studio, a Vue.js-based low-code app builder. Your task is to generate a compact YAML block tree that Studio will render as a live Vue application. Each block in the tree maps to a Vue component (from frappe-ui or Studio) or native html element (div).

BLOCK SCHEMA:
name: componentName          # required — must match catalog exactly
originalElement: div|body    # required for container and root blocks
label: descriptive name
props:                        # component-specific props (flow style preferred)
  key: value
style:                        # panel-editable CSS (see STYLE PROPERTY ROUTING below)
  key: value
rstyle:                       # raw CSS for properties not in the style panel
  key: value
mstyle:                       # mobile style overrides
  key: value
tstyle:                       # tablet style overrides
  key: value
slots:                        # componentSlots for frappe-ui components that hold child content
  slotName: ...
c:                            # children list
- name: ...

ROOT BLOCK:
Always start with:
name: div
originalElement: body
label: body
style: {{display: flex, flexDirection: column, flexShrink: 0, width: inherit, overflowX: hidden, height: 100%}}
c:
- ...

LAYOUT CONTAINERS (CRITICAL — originalElement is required or children won't render):
name: container
originalElement: div
label: container
style: {{display: flex, flexDirection: row|column, gap: ..., padding: ...}}
c:
- ...
- Use container for all inner layout wrappers — never use "div" as name for inner blocks
- flexDirection: row for horizontal layouts, column for vertical
- Use gap, padding for spacing. width: 100% for full-width sections. flex: 1 to fill space.

{STYLING_RULES}

{COMPONENT_CATALOG}

{OUTPUT_FORMAT_RULES}

RULES:
- name must exactly match a component from the catalog above (or "div" for root, "container" for inner wrappers)
- style keys must be camelCase CSS (backgroundColor, borderRadius, fontSize, etc.)
- Do NOT include id (componentId is auto-generated by Studio)
- Do NOT include parentBlock
- Omit keys whose value is null, empty string, empty dict, or empty list
- Keep props to only what's relevant to the description

EXAMPLE — "A login form with email, password and a submit button":
name: div
originalElement: body
label: body
style: {{display: flex, flexDirection: column, flexShrink: 0, width: inherit, overflowX: hidden, height: 100%}}
c:
- name: container
  originalElement: div
  label: page
  style: {{display: flex, flexDirection: column, alignItems: center, justifyContent: center, flex: 1, padding: 24px}}
  c:
  - name: container
    originalElement: div
    label: card
    style: {{display: flex, flexDirection: column, gap: 16px, width: 100%, maxWidth: 400px, padding: 32px, backgroundColor: 'var(--surface-white)', borderRadius: '0.75rem'}}
    c:
    - name: TextBlock
      props: {{text: Sign In, tag: h2, fontSize: text-2xl}}
      style: {{fontWeight: '600', color: 'var(--ink-gray-9)'}}
    - name: TextInput
      props: {{placeholder: Email address}}
    - name: FormControl
      props: {{type: password, label: Password, placeholder: Enter password}}
    - name: Button
      props: {{label: Sign In, variant: solid}}
"""


MODIFY_SYSTEM_PROMPT = f"""You are an expert UI editor for Frappe Studio. You will receive the YAML of a selected block and a user request. Return a modified version of that block.

MODIFICATION RULES:
- Preserve ALL id (componentId) values exactly as given — never change or omit them
- Change ONLY what the user explicitly requests; leave everything else untouched
- Return the COMPLETE block structure starting from the provided root node

{COMPONENT_CATALOG}

{STYLING_RULES}

{OUTPUT_FORMAT_RULES}
"""


def call_llm(messages: list, model: str, task_tier: str, api_key: str, stream: bool = False):
	params = TASK_PARAMS[task_tier]
	return litellm.completion(model=model, messages=messages, api_key=api_key, stream=stream, **params)


def _emit(event_suffix: str, page_id: str, user: str, prefix: str = "ai_generation", **kwargs):
	frappe.publish_realtime(
		f"{prefix}_{event_suffix}_{page_id}",
		{"page_id": page_id, **kwargs},
		user=user,
	)


def _progress_stage(content: str) -> str | None:
	"""Extract a human-readable stage from the tail of a partial YAML stream."""
	lookback = content[-400:]
	for section_type in ("section", "nav", "header", "footer"):
		if lookback.rfind(f"label: {section_type}") != -1 or lookback.rfind(f"name: {section_type}") != -1:
			return f"Building {section_type}…"
	return None


def run_generation_job(prompt: str, model: str, page_id: str, user: str):
	settings = frappe.get_single("Studio Settings")
	api_key = settings.get_password("ai_api_key", raise_exception=False)

	session = AISession.get_or_create(page_id, model)
	context = session.build_context_string()
	session.add_message("user", prompt, task_type="generate")

	_emit("progress", page_id, user, message=f"Generating with {ModelRegistry.get_label(model)}…")

	system = SYSTEM_PROMPT + (f"\n\n{context}" if context else "")
	content = ""
	try:
		llm_messages = [
			{"role": "system", "content": system},
			{"role": "user", "content": f"Create a page for: {prompt}"},
		]
		for chunk in call_llm(llm_messages, model, "complex", api_key, stream=True):
			delta = chunk.choices[0].delta.content
			if not delta:
				continue
			content += delta
			_emit("stream", page_id, user, chunk=delta)
			stage = _progress_stage(content)
			if stage:
				_emit("progress", page_id, user, message=stage)

		logger.info(f"run_generation_job stream done | model={model} length={len(content)}")
		block = BlockCodec.parse_blocks(content)
		session.add_message("assistant", "Page generated successfully.", task_type="generate")
		_emit("complete", page_id, user, block=block)

	except Exception as e:
		logger.error(f"run_generation_job failed: {e}", exc_info=True)
		frappe.log_error(title="Studio AI: generation error", message=str(e))
		_emit("error", page_id, user, message=str(e))


@frappe.whitelist()
@has_page_write_perm()
def generate_page_from_prompt(prompt: str, model: str | None, page_id: str) -> dict:
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw(_("You do not have permission to modify pages"))

	settings = frappe.get_single("Studio Settings")
	if not settings.get_password("ai_api_key", raise_exception=False):
		frappe.throw(_("OpenRouter API key is not configured. Please set it in Studio Settings."))

	resolved_model = model or ModelRegistry.get_default()

	frappe.enqueue(
		run_generation_job,
		queue="long",
		prompt=prompt,
		model=resolved_model,
		page_id=page_id,
		user=frappe.session.user,
	)

	frappe.local.response.http_status_code = 202
	return {"status": "accepted"}


@frappe.whitelist()
def get_ai_session(page_id: str, model: str | None = None) -> dict:
	session = AISession.get_or_create(page_id, model)
	return {
		"messages": session.get_messages(),
		"selected_model": session._doc.selected_model or "",
	}


@frappe.whitelist()
def clear_ai_session(page_id: str) -> dict:
	session = AISession.get_or_create(page_id)
	session.clear()
	return {"status": "ok"}


def run_modify_job(prompt: str, block_context: str, model: str, page_id: str, user: str, component_id: str):
	settings = frappe.get_single("Studio Settings")
	api_key = settings.get_password("ai_api_key", raise_exception=False)

	session = AISession.get_or_create(page_id, model)
	context = session.build_context_string()
	session.add_message("user", prompt, task_type="modify", component_id=component_id)

	_emit("progress", page_id, user, prefix="ai_modify", message="Updating block…")

	compressed = BlockCodec.strip_context(block_context)
	system = MODIFY_SYSTEM_PROMPT + (f"\n\nConversation history:\n{context}" if context else "")

	content = ""
	try:
		llm_messages = [
			{"role": "system", "content": system},
			{"role": "user", "content": f"Current block:\n{compressed}\n\nRequest: {prompt}"},
		]
		for chunk in call_llm(llm_messages, model, "complex", api_key, stream=True):
			delta = chunk.choices[0].delta.content
			if not delta:
				continue
			content += delta
			_emit("stream", page_id, user, prefix="ai_modify", chunk=delta, component_id=component_id)

		logger.info(f"run_modify_job stream done | model={model} length={len(content)}")
		block = BlockCodec.parse_blocks(content)
		session.add_message("assistant", "Block updated.", task_type="modify", component_id=component_id)
		_emit("complete", page_id, user, prefix="ai_modify", block=block, component_id=component_id)

	except Exception as e:
		logger.error(f"run_modify_job failed: {e}", exc_info=True)
		logger.info(f"Raw LLM Output for Modify: \n{content}\n" + "=" * 40)
		frappe.log_error(title="Studio AI: modify error", message=str(e))
		_emit("error", page_id, user, prefix="ai_modify", message=str(e))


@frappe.whitelist()
@has_page_write_perm()
def modify_block_from_prompt(
	prompt: str, block_context: str, model: str | None, page_id: str, component_id: str
) -> dict:
	settings = frappe.get_single("Studio Settings")
	if not settings.get_password("ai_api_key", raise_exception=False):
		frappe.throw(_("OpenRouter API key is not configured. Please set it in Studio Settings."))

	resolved_model = model or ModelRegistry.get_default()

	frappe.enqueue(
		run_modify_job,
		queue="long",
		prompt=prompt,
		block_context=block_context,
		model=resolved_model,
		page_id=page_id,
		user=frappe.session.user,
		component_id=component_id,
	)

	frappe.local.response.http_status_code = 202
	return {"status": "accepted"}
