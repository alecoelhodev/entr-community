// Leaflet uses [lat, lng]; GeoJSON and the server use [lng, lat].
document.addEventListener("alpine:init", () => {
  Alpine.data("directoryMap", () => {
    // Leaflet objects live outside Alpine's reactive proxies, which break them.
    let map, markers, urls, lastPoint, selectedSlug, loadTimer, searchTimer, loadController;
    const markerBySlug = new Map();

    const pinIcon = (selected) =>
      L.divIcon({
        className: selected ? "map-pin map-pin-selected" : "map-pin",
        iconSize: selected ? [42, 42] : [34, 34],
      });

    // Vendor text: build DOM nodes, never HTML strings (Leaflet sets string tooltips as innerHTML).
    const tooltipContent = ({ name, category }) => {
      const el = document.createElement("span");
      const strong = document.createElement("strong");
      strong.textContent = name;
      el.append(strong, document.createTextNode(` · ${category}`));
      return el;
    };

    return {
      q: "",
      category: "",
      radiusKm: "5",
      notice: "",
      detailOpen: false,

      get showResults() {
        return !this.detailOpen;
      },

      get pageClass() {
        return this.detailOpen ? "detail-open" : "";
      },

      init() {
        const data = this.$el.dataset;
        urls = { geojson: data.geojsonUrl, nearby: data.nearbyUrl, panel: data.panelUrl };
        const center = L.latLng(parseFloat(data.centerLat), parseFloat(data.centerLng));

        map = L.map(this.$refs.map).setView(center, parseInt(data.zoom, 10));
        L.tileLayer(data.tileUrl, {
          maxZoom: 19,
          // OSM's tile policy requires a Referer; the page-wide policy (same-origin) strips it.
          referrerPolicy: "strict-origin-when-cross-origin",
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        markers = L.geoJSON(null, {
          pointToLayer: (feature, latlng) =>
            L.marker(latlng, {
              icon: pinIcon(feature.properties.slug === selectedSlug),
              title: feature.properties.name,
              alt: feature.properties.name,
            }),
          onEachFeature: (feature, layer) => {
            markerBySlug.set(feature.properties.slug, layer);
            layer.bindTooltip(tooltipContent(feature.properties));
            layer.on("click", () => this.openPanel(feature.properties.slug));
          },
        }).addTo(map);

        map.on("moveend", () => {
          clearTimeout(loadTimer);
          loadTimer = setTimeout(() => this.loadMarkers(), 250);
        });
        map.on("click", (e) => {
          lastPoint = e.latlng;
          this.loadNearby();
        });

        this.$watch("category", () => this.reloadAll());
        this.$watch("radiusKm", () => this.loadNearby());
        this.$watch("q", () => {
          clearTimeout(searchTimer);
          searchTimer = setTimeout(() => this.reloadAll(), 300);
        });

        // Until the user clicks, "nearby" means around the default center.
        lastPoint = center;
        this.reloadAll();
      },

      filterParams(extra) {
        const params = new URLSearchParams(extra);
        const q = this.q.trim();
        if (this.category) params.set("category", this.category);
        if (q) params.set("q", q);
        return params;
      },

      reloadAll() {
        this.loadMarkers();
        this.loadNearby();
      },

      async loadMarkers() {
        loadController?.abort();
        loadController = new AbortController();
        const params = this.filterParams({ bbox: map.getBounds().toBBoxString() });
        try {
          const res = await fetch(`${urls.geojson}?${params}`, { signal: loadController.signal });
          if (res.status === 400) {
            const body = await res.json().catch(() => ({}));
            this.notice = body.errors?.bbox
              ? "Zoom in to see businesses."
              : "Check your filters: pick a category from the list and keep the search short.";
            this.clearMarkers();
            return;
          }
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          this.clearMarkers();
          markers.addData(data);
          this.notice = data.features.length ? "" : "No businesses match these filters here.";
        } catch (err) {
          if (err.name !== "AbortError") this.notice = "Could not load businesses.";
        }
      },

      clearMarkers() {
        markers.clearLayers();
        markerBySlug.clear();
      },

      loadNearby() {
        const params = this.filterParams({ lat: lastPoint.lat, lng: lastPoint.lng, radius_km: this.radiusKm });
        htmx.ajax("GET", `${urls.nearby}?${params}`, { target: "#nearby", swap: "innerHTML" });
      },

      async openPanel(slug) {
        this.select(slug);
        const url = urls.panel.replace("__slug__", encodeURIComponent(slug));
        await htmx.ajax("GET", url, { target: "#detail", swap: "innerHTML" });
        // htmx doesn't swap error responses, so an empty target means the request failed.
        if (this.$refs.detail.childElementCount) {
          this.detailOpen = true;
          this.$refs.detail.scrollTop = 0;
        } else {
          this.select(null);
          this.notice = "This business is no longer available.";
        }
      },

      openFromCard(event) {
        const slug = event.target.closest("[data-slug]").dataset.slug;
        const marker = markerBySlug.get(slug);
        if (marker) map.panTo(marker.getLatLng());
        this.openPanel(slug);
      },

      closePanel() {
        this.detailOpen = false;
        this.$refs.detail.replaceChildren();
        this.select(null);
      },

      select(slug) {
        markerBySlug.get(selectedSlug)?.setIcon(pinIcon(false)).setZIndexOffset(0);
        selectedSlug = slug;
        markerBySlug.get(slug)?.setIcon(pinIcon(true)).setZIndexOffset(1000);
      },
    };
  });
});
