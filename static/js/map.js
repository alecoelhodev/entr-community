// Leaflet uses [lat, lng]; GeoJSON and the server use [lng, lat].
document.addEventListener("alpine:init", () => {
  Alpine.data("placesMap", () => {
    // Leaflet objects live outside Alpine's reactive proxies, which break them.
    let map, markers, loadTimer, loadController, geojsonUrl, nearbyUrl;

    return {
      radiusKm: "5",
      error: "",

      init() {
        const data = this.$el.dataset;
        geojsonUrl = data.geojsonUrl;
        nearbyUrl = data.nearbyUrl;

        map = L.map(this.$refs.map).setView([38.7223, -9.1393], 13);
        L.tileLayer(data.tileUrl, {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);
        markers = L.geoJSON(null, {
          onEachFeature: (feature, layer) => layer.bindTooltip(feature.properties.name),
        }).addTo(map);

        map.on("moveend", () => {
          clearTimeout(loadTimer);
          loadTimer = setTimeout(() => this.loadMarkers(), 250);
        });
        map.on("click", (e) => this.loadNearby(e.latlng));
        this.loadMarkers();
      },

      async loadMarkers() {
        loadController?.abort();
        loadController = new AbortController();
        const params = new URLSearchParams({ bbox: map.getBounds().toBBoxString() });
        try {
          const res = await fetch(`${geojsonUrl}?${params}`, { signal: loadController.signal });
          if (res.status === 400) {
            this.error = "Zoom in to see places.";
            markers.clearLayers();
            return;
          }
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          this.error = "";
          markers.clearLayers().addData(await res.json());
        } catch (err) {
          if (err.name !== "AbortError") this.error = "Could not load places.";
        }
      },

      loadNearby(latlng) {
        const params = new URLSearchParams({ lat: latlng.lat, lng: latlng.lng, radius_km: this.radiusKm });
        htmx.ajax("GET", `${nearbyUrl}?${params}`, { target: "#nearby", swap: "innerHTML" });
      },
    };
  });
});
