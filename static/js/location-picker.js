// Leaflet uses [lat, lng]; the form posts separate lat/lng fields.
document.addEventListener("alpine:init", () => {
  Alpine.data("locationPicker", () => {
    // Leaflet objects live outside Alpine's reactive proxies, which break them.
    let map, marker;

    return {
      label: "",

      init() {
        const data = this.$el.dataset;
        const current = this.readInputs();
        const center = current || [parseFloat(data.defaultLat), parseFloat(data.defaultLng)];

        map = L.map(this.$refs.map).setView(center, current ? 16 : 13);
        L.tileLayer(data.tileUrl, {
          maxZoom: 19,
          // OSM's tile policy requires a Referer; the page-wide policy (same-origin) strips it.
          referrerPolicy: "strict-origin-when-cross-origin",
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        if (current) this.place(current, false);
        map.on("click", (e) => this.place([e.latlng.lat, e.latlng.lng], true));
      },

      readInputs() {
        const lat = parseFloat(this.$refs.lat.value);
        const lng = parseFloat(this.$refs.lng.value);
        const valid = Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
        return valid ? [lat, lng] : null;
      },

      place(latlng, writeInputs) {
        if (!marker) {
          marker = L.marker(latlng, { icon: L.divIcon({ className: "map-pin map-pin-selected", iconSize: [42, 42] }) }).addTo(map);
        } else {
          marker.setLatLng(latlng);
        }
        if (writeInputs) {
          this.$refs.lat.value = latlng[0].toFixed(6);
          this.$refs.lng.value = latlng[1].toFixed(6);
        }
        this.label = `Pin placed at ${latlng[0].toFixed(4)}, ${latlng[1].toFixed(4)}`;
      },

      syncFromInputs() {
        const current = this.readInputs();
        if (current) {
          this.place(current, false);
          map.panTo(current);
        }
      },
    };
  });
});
