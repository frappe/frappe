// Symlink node_modules/frappe-ui -> the local ../frappe-ui checkout so EVERY
// resolver consumes one copy: Vite (JS), Node (Tailwind's config loader,
// frappe-ui/vite plugin), and vue-tsc all follow the same files. A Vite alias
// would only cover the Vite door and leave Node-loaded tooling (Tailwind
// preset, etc.) resolving the published package.
//
// Run via `yarn dev:frappe-ui`. Idempotent. `yarn dev` / `yarn build` (or
// `yarn install`) restore the published package, so switching back is automatic.
import { lstatSync, readlinkSync, rmSync, symlinkSync, unlinkSync, existsSync } from "node:fs"
import { dirname, resolve, relative } from "node:path"
import { fileURLToPath } from "node:url"
import { execSync } from "node:child_process"

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const checkout = resolve(frontendDir, "../frappe-ui")
const linkPath = resolve(frontendDir, "node_modules/frappe-ui")
const relTarget = relative(dirname(linkPath), checkout)

if (!existsSync(resolve(checkout, "package.json"))) {
	console.error(`✗ No local frappe-ui checkout at ${checkout}`)
	console.error("  Initialize the submodule (git submodule update --init frappe-ui),")
	console.error("  or use `yarn dev` for the published package.")
	process.exit(1)
}

// The checkout's own deps aren't provided by the app install (no workspace
// hoisting), so imports inside its source resolve from checkout/node_modules.
// .yarn-integrity marks a completed install; a bare node_modules doesn't count.
if (!existsSync(resolve(checkout, "node_modules/.yarn-integrity"))) {
	console.log("… Installing frappe-ui checkout dependencies")
	// --pure-lockfile: don't rewrite the checkout's committed yarn.lock
	execSync("yarn install --pure-lockfile", { cwd: checkout, stdio: "inherit" })
}

const stat = lstatSync(linkPath, { throwIfNoEntry: false })
if (stat?.isSymbolicLink() && resolve(dirname(linkPath), readlinkSync(linkPath)) === checkout) {
	console.log("✓ frappe-ui already linked to local checkout")
	process.exit(0)
}

// Replace whatever is there — a published install dir or a stale link. A
// symlink must be removed with unlinkSync (never recurse into the checkout it
// points at); a real install dir is a reinstallable artifact, safe to rm -rf.
if (stat?.isSymbolicLink()) unlinkSync(linkPath)
else if (stat) rmSync(linkPath, { recursive: true, force: true })
symlinkSync(relTarget, linkPath)
console.log(`✓ Linked node_modules/frappe-ui -> ${relTarget} (local checkout)`)
