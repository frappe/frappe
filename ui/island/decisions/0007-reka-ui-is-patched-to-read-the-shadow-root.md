# reka-ui is patched to read the shadow root

frappe-ui's overlays — Dialog, Popover, Select, Tooltip — are reka-ui's
`DismissableLayer`. That layer finds the other layers with
`ownerDocument.querySelectorAll` and listens for dismissal on the document.

Neither reaches inside a shadow root. A layer in an island is invisible to the
document query, and its events arrive at the document retargeted to the shadow
host. So a popover opened over a dialog reads as outside that dialog, and the
click that opens the popover closes the dialog under it.

## Decision

`ui/patches/reka-ui+<version>.patch` makes the layer read the tree it lives in.
`getRootNode()` answers the shadow root inside an island and the document
everywhere else, so nothing outside an island changes. The layer listens on both
its own root and the document, and ignores the document's retargeted copy of an
event it already handled.

reka-ui is the app's dependency, because the app bundles frappe-ui
([0001](0001-an-app-bundles-its-own-island.md)). So the patch is applied by the
app, from this package, in its `postinstall`:

```jsonc
"postinstall": "patch-package && patch-package --patch-dir node_modules/@framework/ui/patches"
```

One copy of the patch serves every island host, and the version in its file name
is the version it was made against. patch-package matches that exactly and warns
on any other, so a reka-ui bump reports the patch rather than dropping it.

This is the shape of a fix that belongs upstream, tracked as
`unovue/reka-ui#1667`. The patch retires the release it lands in.

## Rejected: portal the overlays to the document

Leave reka-ui alone and let overlays render in `<body>`, where its document
queries are right.

An overlay outside the shadow root is outside the island's stylesheet, so it
draws unstyled. Copying the sheet to the document reintroduces exactly the leak
the shadow root is there to prevent.

## Rejected: keep the fix in framework

Framework holds `patches/reka-ui+<version>.patch` and applies it on its own
install.

Framework does not install reka-ui and does not render an overlay. The patch
would sit in a tree where nothing proves it still applies.
