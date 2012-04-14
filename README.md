## wnframework

Full-stack web application framework that uses python/mysql on the server side and a tightly integrated client side library. Primarily built for erpnext.

Projects: [erpnext](http://erpnext.org) | [webnotes/erpnext](https://github.com/webnotes/erpnext)

## Setup

- In your application root, set wnframework folder as the "lib" folder.
- Copy index.cgi, build.json, wnf.py in the application root
- update "conf.py" with database, email authentication info

## wnf.py

wnf.py is the command line utility to build client side files. Usually all client-side files
that are common are build in js/all-web.js (for non logged in users) or js/all-app.js (for logged in users)

## License

wnframework is freely available to use under the MIT License