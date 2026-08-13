// The one script the editor shows before there are any: it fills the editor's
// slot in the empty state, and it is the worked example in the reference. One
// copy, so the two can never teach different things.
export const EXAMPLE_SCRIPT = `import { toast } from 'frappe-ui'

export default {
  refresh(page) {
    page.quickActions.add(
      {
        label: 'Renew',
        onClick: () => toast.success('Renewed'),
      },
      { before: 'email' },
    )
  },
}`;
