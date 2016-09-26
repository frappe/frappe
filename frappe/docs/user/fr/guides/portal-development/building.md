# Building the site

To make the pages to be served on the web, they must first be synced with the database. This is done by running:

    bench --site sitename sync-www

To re-build the site

    bench --site sitename --force sync-www

Clearing the website cache

    bench --site sitename clear-website-cache

{next}
