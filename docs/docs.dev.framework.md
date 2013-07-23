---
{
	"_label": "Framework",
	"_toc": [
		"docs.dev.framework.server",
		"docs.dev.framework.client"
	]
}
---
wnframework has two major libraries one on the client and other on the server.

### Server

The server-side functions are called by the web server (Apache HTTPD) when a user make a web request. The framework handles user authentication, sessions, permissions, business logic and much more.

Serverside functions are also called when static website pages are generated and via a scheduler for triggering scheduled events.

### Client

Once the user is logged in, a javascript based application is loaded. This application communicates with the server to display data, forms, trigger events, run reports etc.

The application is built on standard 3rd party javascript tools like jQuery, Bootstrap,
SlickGrid and others.