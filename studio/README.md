<div align="center">

<img src="https://github.com/user-attachments/assets/5f1cd3ee-9985-4385-8ac1-a984f1e66979" height="80" lt="Frappe Studio Logo">

<h1>Frappe Studio</h1>

**Visual App Builder for the Frappe Framework**

<div>
    <picture>
        <img width="1402" alt="Frappe Studio Screenshot" src="https://github.com/user-attachments/assets/2177dba2-2d4d-4c4b-95bd-bdd6c875278e">
    </picture>
</div>
</div>

⚠️ **WARNING**: This project is in a very early development stage. Expect breaking changes, incomplete features, and bugs. Not recommended for production use yet.

Watch a demo [here](https://www.youtube.com/live/BMjG0Dn39DM?si=jmaeUWtfYy4TS3ap&t=15360)

### Vision

Frappe Studio aims to improve how developers build applications with the Frappe Framework.

### Current Features

- Drag & drop layout builder with frappe-ui components
- Wire Frappe Framework data sources in the app using minimum configurations
- Edit props and slots for any component with the powerful editor
- Faster layout creation with form and CRUD utilities
- Write page scripts (mirroring vue <script setup>) to add reactive state, computed values, watchers & handlers, usable across props, styles and events
- Generate and modify pages with the built-in AI assistant
- Use custom Vue components from the studio folder of your app in your bench
- Export apps to your app's source and build them for production, served by Studio at their own route

### Under the Hood

- [Frappe Framework](https://github.com/frappe/frappe): A full-stack web application framework.
- [Frappe UI](https://github.com/frappe/frappe-ui): A Vue-based UI library, to provide a modern user interface.


## Installation

### Local Setup

1. [Setup Bench](https://docs.frappe.io/framework/user/en/installation). Studio needs Node `>=20.19` (or `>=22.12`).
1. In the frappe-bench directory, run `bench start` and keep it running.
1. Open a new terminal session and cd into `frappe-bench` directory and run following commands:
```bash
bench get-app studio
bench new-site studio.localhost --install-app studio
bench browse studio.localhost --user Administrator
```
1. Access the studio page at `studio.localhost:8000/studio` in your web browser.

To use the AI assistant, set your OpenRouter API key in Studio Settings.

**For Frontend Development & Exported Apps**

You need this setup to work on Studio's frontend, and to build standard (exported) apps, whose pages and scripts live in your Frappe app's `studio` folder — the editor loads them off disk through the vite dev server.

1. Enable developer mode, allow the dev server's requests, and install dev dependencies:
```bash
bench set-config -g developer_mode 1
bench --site studio.localhost set-config ignore_csrf 1
bench setup requirements --dev
```
1. Open a new terminal session and run the following commands:
```bash
cd frappe-bench/apps/studio
yarn install
yarn dev --host
```
1. Now, you can access the site on vite dev server at `http://studio.localhost:8080` (the port shifts along with your bench's `webserver_port`)
1. In one more terminal session, you can start the watcher and keep it running alongside `bench start`:
```bash
bench --site studio.localhost watch-studio
```
It watches the `studio` folder of every installed app and imports changed app/page/component JSON into the database, so apps edited on disk (by hand, the CLI or an AI agent) show up in the editor without a `bench migrate`. Deletions are not synchronized, so remove the corresponding database record separately. Page scripts don't need it — vite hot-reloads the `.ts` files straight off disk.

**Note:** Exported apps can only be edited on a local setup with the dev server running. On a production site they only run, they can't be edited. We will be adding customization support for standard apps soon.

**Note:** You'll find all the code related to Studio's frontend inside `frappe-bench/apps/studio/frontend`

### Bench Commands

```bash
bench build-studio-app <app-name>   # build an app for production
bench --site <site-name> watch-studio # long running watcher to sync app/page/component JSON edited in files to DB
```

<h2></h2>

<br>
<br>
<div align="center">
	<a href="https://frappe.io" target="_blank">
		<picture>
			<source media="(prefers-color-scheme: dark)" srcset="https://frappe.io/files/Frappe-white.png">
			<img src="https://frappe.io/files/Frappe-black.png" alt="Frappe Technologies" height="28"/>
		</picture>
	</a>
</div>

