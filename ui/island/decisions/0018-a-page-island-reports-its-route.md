# A page island reports its route

A page island takes the part of the URL below its page as `route` and `query` ([0012](0012-a-desk-page-can-be-an-island.md)). That covers a link into the island, a reload and the Back button. It does not cover a link inside the island. An island with pages of its own, such as a Studio app, moves between them on its own router, and the URL on screen stays where the reader came in. A reload or a shared link then opens the wrong page, and Back leaves the island.

## Decision

A page island reports where it navigated with a `route` event, `(route, query)`, in the shape it receives them: the segments below the page, and the query as an object.

Desk sets its URL from the report with `frappe.set_route`, so the move is one history entry, like any desk navigation. The route change comes back to the island as a props update. That route is the one it is already on, so it does nothing.

The island reports a navigation it made, never the one it started on. The first route is desk's own. A redirect the island makes on its first navigation is not reported either, so the URL keeps the page the reader asked for.

Like `title` and `actions` ([0010](0010-a-page-island-reports-title-and-actions.md)), it is a plain event. A host that has no URL of its own binds nothing.

## Rejected: the island calls `host.navigate`

The host context already has `navigate(route)`, which routes desk to one of its pages. The island would have to build the full desk route, page name included. It does not know which page draws it, and the same island can sit behind several pages, or in a host that is not desk.
