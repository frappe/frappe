// A fourth entry that imports nothing. Every entry gets the Tailwind stub, so
// without this one `tone.js` would share the stub's chunk, which every entry
// imports anyway.
export function mount() {
	return { update() {}, unmount() {} };
}
