// Opening a type's plain view from the switcher skips the default for that one visit.
// The flag lives for one navigation; a reload or Back to the bare address meets the default again.
let skipped: string | null = null;

/** The next bare address of `doctype` opens its plain view instead of the person's default view. */
export function skipDefaultOnce(doctype: string): void {
	skipped = doctype;
}

/** True once for the doctype the flag was set for. */
export function consumeSkip(doctype: string): boolean {
	const skips = skipped === doctype;
	if (skips) skipped = null;
	return skips;
}

export function clearSkip(): void {
	skipped = null;
}
