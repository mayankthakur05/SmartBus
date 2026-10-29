/**
 * SmartBus — Client-side Application Script
 * Communicates with Flask backend APIs via Fetch API.
 * Dynamically loads stops, manages search form validation,
 * handles 1-hour departure time filtering, highlights fastest bus recommendations,
 * and renders route timelines.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Form Controls
  const sourceSelect = document.getElementById("source-select");
  const destSelect = document.getElementById("destination-select");
  const busTypeSelect = document.getElementById("bus-type-select");
  const departureTimeInput = document.getElementById("departure-time-input");
  const clearTimeBtn = document.getElementById("clear-time-btn");
  const swapBtn = document.getElementById("swap-stops-btn");
  const searchForm = document.getElementById("bus-search-form");
  const searchBtn = document.getElementById("search-btn");
  const validationAlert = document.getElementById("validation-alert");
  const validationMsg = document.getElementById("validation-message");

  // Results Section & Controls
  const resultsSection = document.getElementById("results-section");
  const resultsGrid = document.getElementById("results-grid");
  const resultsSourceLabel = document.getElementById("results-source-label");
  const resultsDestLabel = document.getElementById("results-dest-label");
  const resultsTotalCount = document.getElementById("results-total-count");

  // Time Window Banner
  const timeWindowBanner = document.getElementById("time-window-banner");
  const timeWindowRange = document.getElementById("time-window-range");
  const timeWindowStop = document.getElementById("time-window-stop");
  const clearTimeFilterBtn = document.getElementById("clear-time-filter-btn");

  // States
  const loadingState = document.getElementById("results-loading");
  const emptyState = document.getElementById("results-empty");
  const emptySourceLabel = document.getElementById("empty-source");
  const emptyDestLabel = document.getElementById("empty-dest");
  const emptyDescription = document.getElementById("empty-description");
  const emptyClearTimeBtn = document.getElementById("empty-clear-time-btn");

  const errorState = document.getElementById("results-error");
  const errorTitle = document.getElementById("error-title");
  const errorDesc = document.getElementById("error-description");
  const retryBtn = document.getElementById("retry-search-btn");

  const sortSelect = document.getElementById("sort-select");
  const filterPills = document.querySelectorAll(".filter-pills .pill-btn");

  // Modal Elements
  const routeModal = document.getElementById("route-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalCloseBtnFooter = document.getElementById("modal-close-btn-footer");
  const modalTitle = document.getElementById("modal-title");
  const modalSubtitle = document.getElementById("modal-subtitle");
  const modalBusType = document.getElementById("modal-bus-type");
  const modalFullRoute = document.getElementById("modal-full-route");
  const modalJourneySegment = document.getElementById("modal-journey-segment");
  const modalFare = document.getElementById("modal-fare");
  const modalTimeline = document.getElementById("modal-timeline");

  // State
  let currentSearchData = null;
  let activeFilter = "All";

  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Manage Time Input Clear Button visibility
  function updateClearTimeBtn() {
    if (departureTimeInput.value) {
      clearTimeBtn.classList.remove("hidden");
    } else {
      clearTimeBtn.classList.add("hidden");
    }
  }

  departureTimeInput.addEventListener("input", updateClearTimeBtn);
  departureTimeInput.addEventListener("change", updateClearTimeBtn);

  clearTimeBtn.addEventListener("click", () => {
    departureTimeInput.value = "";
    updateClearTimeBtn();
    if (currentSearchData && currentSearchData.time_filter && currentSearchData.time_filter.applied) {
      performSearch();
    }
  });

  if (clearTimeFilterBtn) {
    clearTimeFilterBtn.addEventListener("click", () => {
      departureTimeInput.value = "";
      updateClearTimeBtn();
      performSearch();
    });
  }

  if (emptyClearTimeBtn) {
    emptyClearTimeBtn.addEventListener("click", () => {
      departureTimeInput.value = "";
      updateClearTimeBtn();
      performSearch();
    });
  }

  // 1. Fetch real stops from MongoDB API
  async function loadStops() {
    try {
      const response = await fetch("/api/stops");
      if (!response.ok) throw new Error("Failed to load stops.");
      const data = await response.json();

      if (data.success && Array.isArray(data.stops)) {
        populateSelect(sourceSelect, data.stops, "Select Boarding Stop");
        populateSelect(destSelect, data.stops, "Select Destination Stop");

        // Set intelligent default (LPU -> Jalandhar)
        const hasLPU = data.stops.some(s => s.stop_name === "LPU");
        const hasJal = data.stops.some(s => s.stop_name === "Jalandhar");
        if (hasLPU && hasJal) {
          sourceSelect.value = "LPU";
          destSelect.value = "Jalandhar";
        }
      }
    } catch (err) {
      showValidationError("Could not connect to database for stops list. Please ensure Flask & MongoDB are running.");
    }
  }

  function populateSelect(selectEl, stops, placeholderText) {
    selectEl.innerHTML = `<option value="" disabled selected>${placeholderText}</option>`;
    stops.forEach(stop => {
      const opt = document.createElement("option");
      opt.value = stop.stop_name;
      opt.textContent = `${stop.stop_name} (${stop.stop_id})`;
      selectEl.appendChild(opt);
    });
  }

  // 2. Swap Stops Action
  swapBtn.addEventListener("click", () => {
    const temp = sourceSelect.value;
    sourceSelect.value = destSelect.value;
    destSelect.value = temp;

    hideValidationError();

    swapBtn.classList.add("rotated");
    setTimeout(() => swapBtn.classList.remove("rotated"), 300);

    if (resultsSection.classList.contains("hidden") === false && sourceSelect.value && destSelect.value) {
      performSearch();
    }
  });

  // 3. Validation Helpers
  function showValidationError(message) {
    validationMsg.textContent = message;
    validationAlert.classList.remove("hidden");
    if (window.lucide) window.lucide.createIcons();
  }

  function hideValidationError() {
    validationAlert.classList.add("hidden");
    validationMsg.textContent = "";
  }

  sourceSelect.addEventListener("change", hideValidationError);
  destSelect.addEventListener("change", hideValidationError);

  // 4. Perform Search
  async function performSearch() {
    const source = sourceSelect.value;
    const dest = destSelect.value;
    const busType = busTypeSelect.value;
    const departureTime = departureTimeInput.value;
    const sortBy = sortSelect.value;

    if (!source || !dest) {
      showValidationError("Please select both Origin (Boarding Stop) and Destination.");
      return;
    }

    if (source.trim().toLowerCase() === dest.trim().toLowerCase()) {
      showValidationError("Origin and Destination cannot be the same stop. Please choose different locations.");
      return;
    }

    hideValidationError();

    // Show Results Section and Loading State
    resultsSection.classList.remove("hidden");
    loadingState.classList.remove("hidden");
    emptyState.classList.add("hidden");
    errorState.classList.add("hidden");
    resultsGrid.innerHTML = "";

    resultsSourceLabel.textContent = source;
    resultsDestLabel.textContent = dest;
    resultsTotalCount.textContent = "...";

    // Smooth scroll to results
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const params = new URLSearchParams({
        source: source,
        destination: dest,
        bus_type: activeFilter !== "All" ? activeFilter : (busType !== "Any" ? busType : ""),
        sort_by: sortBy
      });

      if (departureTime && departureTime.trim()) {
        params.append("departure_time", departureTime.trim());
      }

      const response = await fetch(`/api/search?${params.toString()}`);
      const data = await response.json();

      loadingState.classList.add("hidden");

      if (!response.ok || !data.success) {
        showError(data.error || "Failed to search for buses.");
        return;
      }

      currentSearchData = data;
      renderSearchResults(data);

    } catch (err) {
      loadingState.classList.add("hidden");
      showError("A network error occurred while communicating with the SmartBus server.");
    }
  }

  // 5. Render Results Cards
  function renderSearchResults(data) {
    const results = data.results || [];
    resultsTotalCount.textContent = results.length;

    // Time window banner
    if (data.time_filter && data.time_filter.applied) {
      timeWindowBanner.classList.remove("hidden");
      timeWindowRange.textContent = `${data.time_filter.window_start_12h} to ${data.time_filter.window_end_12h}`;
      timeWindowStop.textContent = data.source;
    } else {
      timeWindowBanner.classList.add("hidden");
    }

    if (results.length === 0) {
      emptySourceLabel.textContent = data.source;
      emptyDestLabel.textContent = data.destination;

      if (data.time_filter && data.time_filter.applied) {
        emptyDescription.innerHTML = `No scheduled buses depart from <strong>${escapeHtml(data.source)}</strong> between <strong>${escapeHtml(data.time_filter.window_start_12h)}</strong> and <strong>${escapeHtml(data.time_filter.window_end_12h)}</strong> for <strong>${escapeHtml(data.destination)}</strong>.`;
        emptyClearTimeBtn.classList.remove("hidden");
      } else {
        emptyDescription.innerHTML = `No scheduled trips traverse between <strong>${escapeHtml(data.source)}</strong> and <strong>${escapeHtml(data.destination)}</strong> in this direction.`;
        emptyClearTimeBtn.classList.add("hidden");
      }

      emptyState.classList.remove("hidden");
      resultsGrid.innerHTML = "";
      if (window.lucide) window.lucide.createIcons();
      return;
    }

    emptyState.classList.add("hidden");
    resultsGrid.innerHTML = "";

    results.forEach((bus, index) => {
      const card = createBusCard(bus, index, data.source, data.destination);
      resultsGrid.appendChild(card);
    });

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function createBusCard(bus, index, searchSource, searchDest) {
    const card = document.createElement("article");
    const isFastest = Boolean(bus.is_fastest);
    card.className = `bus-card ${isFastest ? "fastest-card" : ""}`;
    card.setAttribute("data-trip-id", bus.trip_id);

    const isAc = (bus.bus_type || "").toUpperCase() === "AC";
    const typeBadgeClass = isAc ? "badge-ac" : "badge-non-ac";
    const isDirect = bus.intermediate_stops_count === 0;

    const depDisplay = bus.departure_time_12h && bus.departure_time_12h !== "Time unavailable" 
      ? bus.departure_time_12h 
      : bus.departure_time;

    const arrDisplay = bus.arrival_time_12h && bus.arrival_time_12h !== "Time unavailable" 
      ? bus.arrival_time_12h 
      : bus.arrival_time;

    card.innerHTML = `
      <div class="bus-card-header">
        <div class="bus-identity">
          <h3 class="bus-name">${escapeHtml(bus.bus_name)}</h3>
          <span class="bus-operator">
            <i data-lucide="building-2" class="inline-icon"></i>
            ${escapeHtml(bus.operator)}
          </span>
        </div>
        <div class="bus-badges">
          ${isFastest ? `<span class="badge badge-fastest"><i data-lucide="zap" class="inline-icon"></i> Fastest Journey</span>` : ""}
          ${isDirect ? `<span class="badge badge-direct"><i data-lucide="sparkles" class="inline-icon"></i> Direct</span>` : ""}
          <span class="badge ${typeBadgeClass}">${escapeHtml(bus.bus_type)}</span>
        </div>
      </div>

      <div class="bus-route-overview">
        <i data-lucide="git-branch" class="inline-icon text-muted"></i>
        <span>Scheduled Trip Corridor: <strong>${escapeHtml(bus.full_trip_source)}</strong> → <strong>${escapeHtml(bus.full_trip_destination)}</strong></span>
      </div>

      <div class="bus-metrics-grid">
        <div class="metric-col">
          <span class="metric-label">Departure</span>
          <span class="metric-value">${escapeHtml(depDisplay)}</span>
          <span class="metric-sub">${escapeHtml(bus.source_stop)}</span>
        </div>

        <div class="metric-col">
          <span class="metric-label">Arrival</span>
          <span class="metric-value">${escapeHtml(arrDisplay)}</span>
          <span class="metric-sub">${escapeHtml(bus.destination_stop)}</span>
        </div>

        <div class="metric-col">
          <span class="metric-label">Est. Duration</span>
          <span class="metric-value ${isFastest ? "duration-fastest" : ""}">${escapeHtml(bus.duration_display)}</span>
          <span class="metric-sub">${isFastest ? "Fastest Option" : (bus.duration_minutes ? "Calculated" : "Timetable")}</span>
        </div>

        <div class="metric-col">
          <span class="metric-label">Stops</span>
          <span class="metric-value">${bus.intermediate_stops_count}</span>
          <span class="metric-sub">${isDirect ? "Direct Route" : "Intermediate"}</span>
        </div>

        <div class="metric-col">
          <span class="metric-label">Ticket Fare</span>
          <span class="metric-value fare-highlight">${escapeHtml(bus.fare_display)}</span>
          <span class="metric-sub">${bus.fare !== null ? "Exact Rate" : "Unmapped"}</span>
        </div>
      </div>

      <div class="recommendation-callout ${isFastest ? "fastest-callout" : ""}">
        <i data-lucide="${isFastest ? "zap" : "sparkles"}" class="rec-icon"></i>
        <div class="rec-text">
          <strong>Why this bus:</strong> ${escapeHtml(bus.recommendation_reason)}
        </div>
      </div>

      <div class="bus-card-footer">
        <span class="trip-id-tag">Trip #${escapeHtml(bus.trip_id)} • Bus #${escapeHtml(bus.bus_id)}</span>
        <button type="button" class="btn btn-secondary btn-sm view-route-btn" data-trip="${escapeHtml(bus.trip_id)}" data-src="${escapeHtml(searchSource)}" data-dst="${escapeHtml(searchDest)}">
          <i data-lucide="milestone"></i>
          <span>View Route</span>
        </button>
      </div>
    `;

    const viewRouteBtn = card.querySelector(".view-route-btn");
    viewRouteBtn.addEventListener("click", () => {
      openRouteModal(bus.trip_id, searchSource, searchDest);
    });

    return card;
  }

  // 6. View Route Modal
  async function openRouteModal(tripId, source, dest) {
    modalTimeline.innerHTML = `<div class="spinner" style="margin: 2rem auto;"></div>`;
    modalTitle.textContent = "Loading Route Stops...";
    modalSubtitle.textContent = `Trip #${tripId}`;
    routeModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";

    try {
      const params = new URLSearchParams({ source, destination: dest });
      const response = await fetch(`/api/route/${tripId}?${params.toString()}`);
      const data = await response.json();

      if (!response.ok || !data.success) {
        modalTimeline.innerHTML = `<p class="text-danger" style="text-align: center; padding: 2rem;">${escapeHtml(data.error || "Failed to load route.")}</p>`;
        return;
      }

      modalTitle.textContent = `${data.bus_name} (${data.operator})`;
      modalSubtitle.textContent = `Trip #${data.trip_id} • ${data.direction || "Scheduled Corridor"}`;
      modalBusType.textContent = data.bus_type;
      modalFullRoute.textContent = `${data.full_source} → ${data.full_destination}`;
      modalJourneySegment.textContent = `${source} → ${dest}`;
      modalFare.textContent = data.journey_fare_display;

      renderTimeline(data.stops);

      if (window.lucide) window.lucide.createIcons();

    } catch (err) {
      modalTimeline.innerHTML = `<p class="text-danger" style="text-align: center; padding: 2rem;">Error fetching route details.</p>`;
    }
  }

  function renderTimeline(stops) {
    if (!stops || stops.length === 0) {
      modalTimeline.innerHTML = `<p style="text-align: center; color: var(--slate-500);">No stop details found.</p>`;
      return;
    }

    modalTimeline.innerHTML = "";

    stops.forEach(stop => {
      const node = document.createElement("div");
      node.className = `timeline-node ${stop.role}`;

      let roleBadgeHtml = "";
      if (stop.role === "origin") {
        roleBadgeHtml = `<span class="role-badge origin">Origin Boarding</span>`;
      } else if (stop.role === "destination") {
        roleBadgeHtml = `<span class="role-badge destination">Destination Drop</span>`;
      }

      const timeDisplay = stop.arrival_time_12h && stop.arrival_time_12h !== "Time unavailable"
        ? stop.arrival_time_12h
        : stop.arrival_time;

      node.innerHTML = `
        <div class="timeline-pin"></div>
        <div class="timeline-content">
          <div class="timeline-stop-name">
            ${escapeHtml(stop.stop_name)}
            ${roleBadgeHtml}
          </div>
          <span class="timeline-seq">Stop Sequence #${stop.sequence}</span>
        </div>
        <div class="timeline-time">
          <i data-lucide="clock" class="inline-icon text-muted"></i>
          ${escapeHtml(timeDisplay)}
        </div>
      `;

      modalTimeline.appendChild(node);
    });
  }

  function closeRouteModal() {
    routeModal.classList.add("hidden");
    document.body.style.overflow = "";
  }

  modalCloseBtn.addEventListener("click", closeRouteModal);
  modalCloseBtnFooter.addEventListener("click", closeRouteModal);
  routeModal.addEventListener("click", (e) => {
    if (e.target === routeModal) closeRouteModal();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !routeModal.classList.contains("hidden")) {
      closeRouteModal();
    }
  });

  // 7. Error Handling Display
  function showError(message) {
    errorTitle.textContent = "Search Error";
    errorDesc.textContent = message;
    errorState.classList.remove("hidden");
    if (window.lucide) window.lucide.createIcons();
  }

  retryBtn.addEventListener("click", performSearch);

  // 8. Form Submit
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    performSearch();
  });

  // 9. Sorting & Filtering Controls
  sortSelect.addEventListener("change", () => {
    if (currentSearchData) {
      performSearch();
    }
  });

  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeFilter = pill.getAttribute("data-filter");
      if (currentSearchData) {
        performSearch();
      }
    });
  });

  // Helper
  function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Load stops on startup
  loadStops();
  updateClearTimeBtn();
});
