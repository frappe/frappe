// The one script the editor shows before there are any: it fills the editor's
// slot in the empty state, and it is the worked example in the reference. One
// copy, so the two can never teach different things.
//
// Every key here is load-bearing, which is why the example carries all four:
// `name` is the identity `hide`/`update`/`order` address and the key a second
// `add` dedupes on; `icon` is what an overflowed action renders as; and the
// callback is **`run`**, not `onClick` — the host invokes `action.run?.(page)`,
// so an `onClick` is accepted by the type's index signature, dropped in
// silence, and leaves a button that does nothing.
export const EXAMPLE_SCRIPT = `import { toast } from 'frappe-ui'

export default {
  refresh(page) {
    page.quickActions.add(
      {
        name: 'renew',
        label: 'Renew',
        icon: 'lucide-refresh-cw',
        run: () => toast.success('Renewed'),
      },
      { before: 'email' },
    )
  },
}`;
