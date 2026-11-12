// The text a Geolocation field reads as, in Details and in a panel row.
import { describe, expect, it } from "vitest";
import { geolocationSummary } from "../geolocationSummary";

const point = (lng: number, lat: number) => ({
  type: "Feature",
  properties: {},
  geometry: { type: "Point", coordinates: [lng, lat] },
});
const collection = (...features: unknown[]) =>
  JSON.stringify({ type: "FeatureCollection", features });

describe("geolocationSummary", () => {
  it("reads nothing for an empty value", () => {
    expect(geolocationSummary(null)).toBe("");
    expect(geolocationSummary(undefined)).toBe("");
    expect(geolocationSummary("")).toBe("");
  });

  it.each([
    [collection(point(77.5946, 12.9716)), "12.97160°N, 77.59460°E"],
    [JSON.stringify(point(-0.1278, -51.5074)), "51.50740°S, 0.12780°W"],
  ])("gives one point as coordinates", (value, summary) => {
    expect(geolocationSummary(value)).toBe(summary);
  });

  it("counts anything but a single point", () => {
    expect(geolocationSummary(collection(point(1, 2), point(3, 4)))).toBe("2 features");
    expect(
      geolocationSummary(
        collection({ type: "Feature", geometry: { type: "Polygon", coordinates: [] } })
      )
    ).toBe("1 feature");
  });

  it("flags a value that is not JSON", () => {
    expect(geolocationSummary("{oops")).toBe("Invalid GeoJSON");
  });
});
