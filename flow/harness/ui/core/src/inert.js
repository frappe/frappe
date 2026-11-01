// Whether a host hides `el` (inert), through the shadow roots it sits in: a chat mounted as an
// island in a page's panel is inside a shadow root, so closest() stops short of the host's mark
export function isInert(el) {
	for (let node = el; node; node = node.parentElement ?? node.getRootNode?.().host) {
		if (node.inert) return true
	}
	return false
}
