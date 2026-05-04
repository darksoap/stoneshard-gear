const PAGE_SIZE = 30;

const FILTER_TYPE_TO_URL_PARAM: Record<string, string> = {
  rarity: "rarity",
  tier: "tier",
  material: "material",
  "armor-class": "armorClass",
};

function filterTypeToDataAttr(type: string): string {
  if (type === "armor-class") return "armorClass";
  return type;
}

export function initListFilter() {
  const activeFilters: Record<string, Set<string>> = {};

  let currentSort = "name-asc";
  let currentPage = 1;

  function saveStateToUrl() {
    const params = new URLSearchParams();

    for (const [type, values] of Object.entries(activeFilters)) {
      if (values.size > 0) {
        const paramName = FILTER_TYPE_TO_URL_PARAM[type] || type;
        params.set(paramName, Array.from(values).join(","));
      }
    }

    if (currentSort !== "name-asc") {
      params.set("sort", currentSort);
    }

    const newUrl = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;

    window.history.replaceState({}, "", newUrl);
  }

  function loadStateFromUrl() {
    const params = new URLSearchParams(window.location.search);

    for (const [type, urlParam] of Object.entries(FILTER_TYPE_TO_URL_PARAM)) {
      const values = params.get(urlParam);
      if (values) {
        if (!activeFilters[type]) activeFilters[type] = new Set();
        values.split(",").forEach((v) => {
          activeFilters[type].add(v);
          const chip = document.querySelector(
            `.filter-chip[data-filter-type="${type}"][data-value="${v}"]`,
          );
          if (chip) chip.classList.add("active");
        });
      }
    }

    const sort = params.get("sort");
    if (sort) {
      currentSort = sort;
      const select = document.getElementById(
        "sort-select",
      ) as HTMLSelectElement | null;
      if (select) select.value = sort;
    }
  }

  function getVisibleItems(): HTMLElement[] {
    const items = document.querySelectorAll<HTMLElement>(".item-card");
    const visible: HTMLElement[] = [];
    items.forEach((item) => {
      let isVisible = true;
      for (const [type, values] of Object.entries(activeFilters)) {
        if (isVisible && values.size > 0) {
          const value = item.dataset[filterTypeToDataAttr(type)];
          if (!values.has(value!)) isVisible = false;
        }
      }
      if (isVisible) visible.push(item);
    });
    return visible;
  }

  function applyPagination(visibleItems: HTMLElement[]) {
    const loadMoreBtn = document.getElementById("load-more-btn");
    const loadMoreWrap = document.getElementById("load-more-wrap");

    visibleItems.forEach((item, index) => {
      item.classList.toggle("hidden", index >= currentPage * PAGE_SIZE);
    });

    const hasMore = visibleItems.length > currentPage * PAGE_SIZE;
    if (loadMoreWrap) loadMoreWrap.classList.toggle("hidden", !hasMore);
    if (loadMoreBtn) {
      loadMoreBtn.textContent = `加载更多 (${visibleItems.length - currentPage * PAGE_SIZE} 件)`;
    }
  }

  function updateDisplay() {
    currentPage = 1;

    const items = document.querySelectorAll(".item-card");
    let visibleCount = 0;

    items.forEach((item) => {
      let visible = true;

      for (const [type, values] of Object.entries(activeFilters)) {
        if (visible && values.size > 0) {
          const el = item as HTMLElement;
          const value = el.dataset[filterTypeToDataAttr(type)];
          if (!values.has(value!)) visible = false;
        }
      }

      item.classList.toggle("hidden", !visible);
      if (visible) visibleCount++;
    });

    const filteredCountEl = document.getElementById("filtered-count");
    if (filteredCountEl)
      filteredCountEl.textContent = visibleCount.toString();

    const noResultsEl = document.getElementById("no-results");
    if (noResultsEl) noResultsEl.classList.toggle("hidden", visibleCount > 0);

    const gridEl = document.getElementById("results-grid");
    if (gridEl) gridEl.classList.toggle("hidden", visibleCount === 0);

    if (visibleCount > 0) sortItems();
    saveStateToUrl();
  }

  function sortItems() {
    const grid = document.getElementById("results-grid")!;
    const items = Array.from(
      grid.querySelectorAll<HTMLElement>(".item-card:not(.hidden)"),
    );

    items.sort((a, b) => {
      switch (currentSort) {
        case "name-asc":
          return (a.dataset.name || "").localeCompare(
            b.dataset.name || "",
            "zh-CN",
          );
        case "name-desc":
          return (b.dataset.name || "").localeCompare(
            a.dataset.name || "",
            "zh-CN",
          );
        case "tier-asc":
          return (
            parseInt(a.dataset.tier || "0") - parseInt(b.dataset.tier || "0")
          );
        case "tier-desc":
          return (
            parseInt(b.dataset.tier || "0") - parseInt(a.dataset.tier || "0")
          );
        case "price-asc":
          return (
            parseInt(a.dataset.price || "0") -
            parseInt(b.dataset.price || "0")
          );
        case "price-desc":
          return (
            parseInt(b.dataset.price || "0") -
            parseInt(a.dataset.price || "0")
          );
        case "durability-desc":
          return (
            parseInt(b.dataset.durability || "0") -
            parseInt(a.dataset.durability || "0")
          );
        default:
          return 0;
      }
    });

    items.forEach((item) => grid.appendChild(item));

    applyPagination(items);
  }

  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const el = chip as HTMLElement;
      const filterType = el.dataset.filterType!;
      const value = el.dataset.value!;

      if (!activeFilters[filterType]) activeFilters[filterType] = new Set();

      if (activeFilters[filterType].has(value)) {
        activeFilters[filterType].delete(value);
        el.classList.remove("active");
      } else {
        activeFilters[filterType].add(value);
        el.classList.add("active");
      }

      updateDisplay();
    });
  });

  document.getElementById("clear-filters")?.addEventListener("click", () => {
    for (const key of Object.keys(activeFilters)) {
      activeFilters[key].clear();
    }

    document.querySelectorAll(".filter-chip").forEach((chip) => {
      chip.classList.remove("active");
    });

    updateDisplay();
  });

  document.getElementById("sort-select")?.addEventListener("change", (e) => {
    currentSort = (e.target as HTMLSelectElement).value;
    sortItems();
    saveStateToUrl();
  });

  document.getElementById("load-more-btn")?.addEventListener("click", () => {
    currentPage++;
    const visibleItems = getVisibleItems();
    applyPagination(visibleItems);
  });

  loadStateFromUrl();
  updateDisplay();
}
