<div align="center">

<img src="https://github.com/user-attachments/assets/0890fc80-ac2a-48c3-ac94-d2a9387e09cc" height="80" alt="Frappe Studio Logo">

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
- Build reactive apps with dynamic variables, scripts & watcher support

### Under the Hood

- [Frappe Framework](https://github.com/frappe/frappe): A full-stack web application framework.
- [Frappe UI](https://github.com/frappe/frappe-ui): A Vue-based UI library, to provide a modern user interface.


## Installation

### Local Setup

1. [Setup Bench](https://docs.frappe.io/framework/user/en/installation).
1. In the frappe-bench directory, run `bench start` and keep it running.
1. Open a new terminal session and cd into `frappe-bench` directory and run following commands:
```bash
bench get-app studio
bench new-site studio.localhost --install-app studio
bench browse studio.localhost --user Administrator
```
1. Access the studio page at `studio.localhost:8000/studio` in your web browser.

**For Frontend Development**
1. Open a new terminal session and run the following commands:
```bash
cd frappe-bench/apps/studio
yarn install
yarn dev --host
```
1. Now, you can access the site on vite dev server at `http://studio.localhost:8080`

**Note:** You'll find all the code related to Studio's frontend inside `frappe-bench/apps/studio/frontend`

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

