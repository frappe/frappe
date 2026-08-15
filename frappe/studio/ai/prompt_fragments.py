"""Shared prompt / tool-description fragments — a single source of truth for rules that are
cited in BOTH the system prompts (`prompts.py`) and individual tool descriptions
(`agent/tools/*`)."""

TRANSFORM_RULE = (
	"JavaScript that reshapes the fetched result before it becomes {{ <name>.data }}. MUST declare a "
	"function named exactly `transform` taking the raw result — the records array (Document List / "
	"API) or the doc (Document) — and RETURNING the new value. This is where you clean a field for "
	"display (strip HTML from rich text, format a datetime/currency, derive a label), returning records "
	"with the cleaned fields so the layout binds {{ dataItem.<field> }} directly. e.g. 'function transform(data) { return "
	'data.map(row => ({ ...row, label: row.first_name + " " + row.last_name })) }\'.'
)

ON_SUCCESS_RULE = (
	"JavaScript run after a successful fetch. MUST declare a function named exactly `onSuccess` taking "
	"(data). The page context is in scope — variables are refs (write via .value), plus the other "
	"resources and route/router. e.g. 'function onSuccess(data) { rowCount.value = data.length }'."
)

ON_ERROR_RULE = (
	"JavaScript run when the fetch fails. MUST declare a function named exactly `onError` taking "
	"(error). Same page context in scope. e.g. 'function onError(error) { loadFailed.value = true }'."
)

FILTER_FORMAT_RULE = 'Filters as a map, e.g. {"status":"Open"} or {"status":["!=","Closed"]}.'
