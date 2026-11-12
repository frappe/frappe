/** What a Geolocation field reads: `12.97160°N, 77.59460°E` for one point, else `N features`; `""` when unset. */
export function geolocationSummary(value: string | null | undefined): string {
  if (!value) return "";
  try {
    const geo = JSON.parse(value);
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
}
