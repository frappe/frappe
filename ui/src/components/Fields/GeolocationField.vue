<template>
	<div>
		<!-- A read-only TextInput is the display surface: it gives us the label,
		     description, required indicator, error, and size variant for free, and
		     stays consistent with the other FormLayout fields. The value is never
		     typed — clicking opens the map dialog. The input is `readonly` rather
		     than `disabled` even in read-only mode so it can still be clicked to
		     open the View Location dialog (a disabled input swallows clicks). -->
		<TextInput
			:modelValue="coordinateSummary"
			:label="field.label"
			:description="field.description"
			:placeholder="field.readOnly ? '—' : field.placeholder || 'Set location'"
			:required="field.reqd"
			readonly
			class="group"
			:class="canOpen ? '[&_input]:cursor-pointer' : null"
			@click="openModal"
			@keydown.enter.prevent="openModal"
		>
			<template #prefix>
				<span
					class="lucide-map-pin pointer-events-none size-3.5 shrink-0"
					:class="modelValue ? 'text-ink-gray-7' : 'text-ink-gray-5'"
					aria-hidden="true"
				/>
			</template>
			<template v-if="!field.readOnly && modelValue" #suffix>
				<button
					type="button"
					aria-label="Clear"
					data-slot="clear"
					class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					@click.stop="clearLocation"
					@pointerdown.stop
				>
					<span class="lucide-x size-3.5" />
				</button>
			</template>
		</TextInput>

		<!-- Map Dialog -->
		<Dialog
			v-model:open="showModal"
			:title="field.readOnly ? 'View Location' : 'Set Location'"
			size="4xl"
		>
			<!-- If the map libraries fail to load, show a message instead of an
			     empty map (see loadError). -->
			<div
				v-if="loadError"
				class="flex h-[500px] w-full items-center justify-center rounded border border-dashed border-outline-gray-2 p-6 text-center text-p-sm text-ink-gray-6"
			>
				{{ loadError }}
			</div>
			<div v-else :id="mapId" class="h-[500px] w-full rounded" />
			<template #actions>
				<div class="flex items-center justify-end gap-2">
					<Button
						variant="outline"
						:label="field.readOnly ? 'Close' : 'Cancel'"
						@click="showModal = false"
					/>
					<Button
						v-if="!field.readOnly && !loadError"
						variant="solid"
						label="Save"
						@click="saveLocation"
					/>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
// GeoJSON map field, ported from CRM's `Controls/GeolocationControl.vue` into the
// FormLayout field contract: value is the raw GeoJSON string (`modelValue`),
// `field.readOnly` toggles view-only mode, and a save/clear is treated as a
// commit (emits both `update:modelValue` and `change`, like the picker fields).
//
// Every Leaflet import is DYNAMIC — including the marker-image `?url` assets —
// so `fieldTypes.ts`'s static import graph stays Leaflet-free and Leaflet is
// code-split into an async chunk that loads only when a map opens. The library
// ships `leaflet`/`leaflet-draw`/`leaflet.locatecontrol` as DIRECT deps, so
// every consuming app gets them automatically — no app is assumed to install
// them, and apps that never render this field pay no runtime cost. A load
// failure still surfaces as `loadError` rather than throwing silently.
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { Button, Dialog, TextInput } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const showModal = ref(false);

// Set when Leaflet fails to load (unexpected — it's a direct dep, but guard for
// a broken async chunk / network blip); rendered in the dialog in place of the
// map so the failure is visible rather than a silent unhandled rejection.
const loadError = ref<string | null>(null);

// Best-effort device location for a sensible starting center. Uses the native
// Geolocation API directly — no @vueuse dependency (its `useGeolocation` is just
// a reactive wrapper over this), so the shared library carries no extra peer dep
// for one field. Requested once when the dialog opens (clear user intent), never
// on page load. If denied/unavailable the default world view is used, and the
// locate control (top-right) still lets users center on themselves on demand.
const deviceCenter = ref<[number, number] | null>(null);

// Module-scoped counter gives a collision-free DOM id without Math.random().
const mapId = `geo-map-${nextMapId()}`;

// Leaflet instances — populated after dynamic import on first open.
let L: any = null;
let mapInstance: any = null;
let editableLayers: any = null;
let drawControl: any = null;

// One-time guard for the injected icon CSS (see injectMapIconCss).
let iconCssInjected = false;

// ─── Computed ────────────────────────────────────────────────────────────────

const coordinateSummary = computed(() => {
	if (!props.modelValue) return "";
	try {
		const geo = JSON.parse(props.modelValue);
		// Single Point feature or FeatureCollection with one Point.
		const features = geo.type === "FeatureCollection" ? geo.features : [geo];
		const points = features.filter((f: any) => f.geometry?.type === "Point");
		if (features.length === 1 && points.length === 1) {
			const [lng, lat] = points[0].geometry.coordinates;
			const latStr = `${Math.abs(lat).toFixed(5)}°${lat >= 0 ? "N" : "S"}`;
			const lngStr = `${Math.abs(lng).toFixed(5)}°${lng >= 0 ? "E" : "W"}`;
			return `${latStr}, ${lngStr}`;
		}
		const count = features.length;
		return `${count} ${count === 1 ? "feature" : "features"}`;
	} catch {
		return "Invalid GeoJSON";
	}
});

// Open the dialog whenever there is something to do: set a value (editable) or
// view an existing one (read-only). An empty read-only field has nothing to show.
const canOpen = computed(() => Boolean(props.modelValue) || !props.field.readOnly);

function openModal() {
	if (canOpen.value) showModal.value = true;
}

// ─── Map lifecycle ───────────────────────────────────────────────────────────

watch(showModal, (visible) => {
	if (!visible) {
		destroyMap();
		return;
	}
	requestDeviceLocation();
	nextTick(() => initMap());
});

// Device location resolves asynchronously; if it arrives while the map is open
// on an empty value, recenter on it. A saved value keeps its own framing.
watch(deviceCenter, (center) => {
	if (center && showModal.value && mapInstance && !props.modelValue) {
		mapInstance.setView(center, 13);
	}
});

function requestDeviceLocation() {
	if (typeof navigator === "undefined" || !navigator.geolocation) return;
	navigator.geolocation.getCurrentPosition(
		(pos) => {
			deviceCenter.value = [pos.coords.latitude, pos.coords.longitude];
		},
		() => {
			// Permission denied or unavailable — the default center is used.
		},
		{ enableHighAccuracy: false, timeout: 5000, maximumAge: 600000 }
	);
}

// Leaflet and leaflet-draw reference the layers-control icon and the draw-toolbar
// sprite via relative `url()` in their CSS. Vite doesn't rewrite those (the CSS is
// imported as a side-effect), so the browser requests the raw node_modules paths —
// which many host dev servers 403. We mirror the marker-icon fix: resolve each
// asset through Vite (`?url`) and inject overriding CSS so they load anywhere.
// Runs once per process.
async function injectMapIconCss() {
	if (iconCssInjected || typeof document === "undefined") return;
	iconCssInjected = true;

	const [layers, layers2x, sprite, sprite2x, spriteSvg] = await Promise.all([
		import("leaflet/dist/images/layers.png?url"),
		import("leaflet/dist/images/layers-2x.png?url"),
		import("leaflet-draw/dist/images/spritesheet.png?url"),
		import("leaflet-draw/dist/images/spritesheet-2x.png?url"),
		import("leaflet-draw/dist/images/spritesheet.svg?url"),
	]);

	// Geometry must match the upstream CSS exactly: the draw sprite is 300×30
	// (10 tools × 30px) and the per-tool background-position offsets are baked for
	// that size, so background-size has to be 300px 30px on BOTH base and retina.
	// The retina layers icon is a 2x image scaled back to 26px.
	const style = document.createElement("style");
	style.textContent = `
.leaflet-control-layers-toggle { background-image: url(${layers.default}); }
.leaflet-retina .leaflet-control-layers-toggle {
	background-image: url(${layers2x.default});
	background-size: 26px 26px;
}
.leaflet-draw-toolbar a {
	background-image: url(${sprite.default});
	background-image: linear-gradient(transparent, transparent), url(${spriteSvg.default});
	background-size: 300px 30px;
}
.leaflet-retina .leaflet-draw-toolbar a {
	background-image: url(${sprite2x.default});
	background-image: linear-gradient(transparent, transparent), url(${spriteSvg.default});
	background-size: 300px 30px;
}
`;
	document.head.appendChild(style);
}

// Loads Leaflet + plugins on first open and returns the `locate` factory.
// Throws if the map libraries fail to load; initMap() turns that into a
// user-facing loadError.
async function loadLeaflet() {
	if (!L) {
		await import("leaflet/dist/leaflet.css");
		await import("leaflet-draw/dist/leaflet.draw.css");
		const leafletModule: any = await import("leaflet");
		L = leafletModule.default ?? leafletModule;
		await import("leaflet-draw");

		// Fix Vite marker image paths — delete the built-in resolver first, then
		// supply the resolved `?url` strings. Imported dynamically (not at module
		// top level) to keep Leaflet out of the static registry import graph.
		const [iconUrl, iconRetinaUrl, shadowUrl] = await Promise.all([
			import("leaflet/dist/images/marker-icon.png?url"),
			import("leaflet/dist/images/marker-icon-2x.png?url"),
			import("leaflet/dist/images/marker-shadow.png?url"),
		]);
		delete L.Icon.Default.prototype._getIconUrl;
		L.Icon.Default.mergeOptions({
			iconUrl: iconUrl.default,
			iconRetinaUrl: iconRetinaUrl.default,
			shadowUrl: shadowUrl.default,
		});

		// Same path problem for the CSS-referenced toolbar/layers icons.
		await injectMapIconCss();

		// Patch Circle/CircleMarker toGeoJSON to include radius in properties
		// (same patch as Frappe's customize_draw_controls).
		const circleToGeoJSON = L.Circle.prototype.toGeoJSON;
		L.Circle.include({
			toGeoJSON() {
				const feature = circleToGeoJSON.call(this);
				feature.properties = { point_type: "circle", radius: this.getRadius() };
				return feature;
			},
		});
		L.CircleMarker.include({
			toGeoJSON() {
				const feature = circleToGeoJSON.call(this);
				feature.properties = {
					point_type: "circlemarker",
					radius: this.getRadius(),
				};
				return feature;
			},
		});
	}

	await import("leaflet.locatecontrol/dist/L.Control.Locate.min.css");
	const { locate }: any = await import("leaflet.locatecontrol");
	return locate;
}

async function initMap() {
	loadError.value = null;

	let leafletLocate: any;
	try {
		leafletLocate = await loadLeaflet();
	} catch {
		loadError.value = "The map failed to load. Please try again.";
		return;
	}

	// Dialog uses v-if internally — the map div is destroyed on close and
	// recreated on open. destroyMap() on close ensures mapInstance is null here.
	mapInstance = L.map(mapId);

	// ── Tile layers (mirrors Frappe's map_defaults) ──────────────────────────
	const streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
		maxZoom: 19,
		attribution:
			'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
	});
	const satelliteLayer = L.tileLayer(
		"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
		{ attribution: "© Esri © OpenStreetMap Contributors" }
	);
	const labelsLayer = L.tileLayer(
		"https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}{r}.png",
		{
			attribution:
				'© <a href="https://www.stadiamaps.com/">Stadia Maps</a> © <a href="https://www.stamen.com/">Stamen Design</a>',
		}
	);
	const terrainLayer = L.tileLayer(
		"https://tiles.stadiamaps.com/tiles/stamen_terrain_lines/{z}/{x}/{y}{r}.png",
		{
			attribution:
				'© <a href="https://www.stadiamaps.com/">Stadia Maps</a> © <a href="https://www.stamen.com/">Stamen Design</a>',
		}
	);

	streetLayer.addTo(mapInstance);

	L.control
		.layers(
			{ Default: streetLayer, Satellite: satelliteLayer },
			{ Labels: labelsLayer, Terrain: terrainLayer }
		)
		.addTo(mapInstance);

	// ── Locate control ───────────────────────────────────────────────────────
	leafletLocate({ position: "topright" }).addTo(mapInstance);

	editableLayers = new L.FeatureGroup();
	editableLayers.addTo(mapInstance);

	// Draw controls — only in edit mode.
	if (!props.field.readOnly) {
		drawControl = new L.Control.Draw({
			position: "topleft",
			draw: {
				polyline: { shapeOptions: { color: "#4f46e5", weight: 4 } },
				polygon: {
					allowIntersection: false,
					shapeOptions: { color: "#4f46e5" },
				},
				circle: true,
				rectangle: { showArea: false, shapeOptions: { color: "#4f46e5" } },
				circlemarker: true,
				marker: true,
			},
			edit: { featureGroup: editableLayers, remove: true },
		});
		drawControl.addTo(mapInstance);

		mapInstance.on("draw:created", (e: any) => {
			editableLayers.addLayer(e.layer);
		});

		mapInstance.on("draw:deleted", (e: any) => {
			e.layers.eachLayer((l: any) => editableLayers.removeLayer(l));
		});
	}

	reloadData();
}

function reloadData() {
	if (!L || !editableLayers || !mapInstance) return;

	editableLayers.clearLayers();

	// Center on device location if already known, else a neutral world view.
	// A saved value overrides this via fitMap() below; an empty map can also be
	// recentered by the device-location watcher or the locate control.
	if (deviceCenter.value) {
		mapInstance.setView(deviceCenter.value, 13);
	} else {
		mapInstance.setView([20, 0], 2);
	}

	if (!props.modelValue) return;

	try {
		const geoData = JSON.parse(props.modelValue);
		const dataGroup = new L.FeatureGroup().addLayer(
			L.geoJSON(geoData, {
				pointToLayer(geoJsonPoint: any, latlng: any) {
					const pt = geoJsonPoint.properties?.point_type;
					if (pt === "circle") {
						return L.circle(latlng, {
							radius: geoJsonPoint.properties.radius,
						});
					}
					if (pt === "circlemarker") {
						return L.circleMarker(latlng, {
							radius: geoJsonPoint.properties.radius,
						});
					}
					return L.marker(latlng);
				},
			})
		);
		addNonGroupLayers(dataGroup, editableLayers);
		fitMap();
	} catch {
		// Invalid JSON — ignore.
	}
}

function addNonGroupLayers(source: any, target: any) {
	if (source instanceof L.LayerGroup) {
		source.eachLayer((l: any) => addNonGroupLayers(l, target));
	} else {
		target.addLayer(source);
	}
}

function fitMap() {
	mapInstance.invalidateSize();
	const bounds = editableLayers.getBounds();
	if (bounds.isValid()) {
		// fitBounds works for multi-point layers; for a single point the bounds
		// have zero area so we zoom manually instead.
		const ne = bounds.getNorthEast();
		const sw = bounds.getSouthWest();
		if (ne.equals(sw)) {
			mapInstance.setView(ne, 14);
		} else {
			mapInstance.fitBounds(bounds, { padding: [50, 50] });
		}
	}
}

// ─── Actions ─────────────────────────────────────────────────────────────────

// A save/clear is a commit (like the picker fields): sync the value AND emit the
// field's `change`, which the node's `ui.on.change` catches (and the grid `commit`
// in a cell). `FormLayout` itself emits nothing.
function saveLocation() {
	if (!editableLayers) {
		showModal.value = false;
		return;
	}
	const geoJson = editableLayers.toGeoJSON();
	const hasFeatures = geoJson.features?.length > 0;
	const next = hasFeatures ? JSON.stringify(geoJson) : null;
	emit("update:modelValue", next);
	emit("change", next);
	showModal.value = false;
}

function clearLocation() {
	emit("update:modelValue", null);
	emit("change", null);
}

// ─── Cleanup ─────────────────────────────────────────────────────────────────

function destroyMap() {
	if (mapInstance) {
		mapInstance.remove();
		mapInstance = null;
		editableLayers = null;
		drawControl = null;
	}
}

onBeforeUnmount(() => destroyMap());
</script>

<script lang="ts">
// Process-wide counter for unique map container ids (avoids Math.random()).
let mapIdSeq = 0;
function nextMapId() {
	return ++mapIdSeq;
}
</script>
