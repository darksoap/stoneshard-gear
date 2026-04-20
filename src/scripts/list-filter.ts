export interface FilterConfig {
  filterTypes: string[];
  urlParamMap: Record<string, string>;
  extraDataAttrs?: Record<string, string>;
}

export function initListFilter(config: FilterConfig) {
  const activeFilters: Record<string, Set<string>> = {};
  for (const type of config.filterTypes) {
    activeFilters[type] = new Set();
  }

  let currentSort = 'name-asc';

  function saveStateToUrl() {
    const params = new URLSearchParams();

    for (const type of config.filterTypes) {
      if (activeFilters[type].size > 0) {
        const paramName = config.urlParamMap[type] || type;
        params.set(paramName, Array.from(activeFilters[type]).join(','));
      }
    }

    if (currentSort !== 'name-asc') {
      params.set('sort', currentSort);
    }

    const newUrl = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;

    window.history.replaceState({}, '', newUrl);
  }

  function loadStateFromUrl() {
    const params = new URLSearchParams(window.location.search);

    for (const type of config.filterTypes) {
      const paramName = config.urlParamMap[type] || type;
      const values = params.get(paramName);
      if (values) {
        values.split(',').forEach(v => {
          activeFilters[type].add(v);
          const chip = document.querySelector(`.filter-chip[data-filter-type="${type}"][data-value="${v}"]`);
          if (chip) chip.classList.add('active');
        });
      }
    }

    const sort = params.get('sort');
    if (sort) {
      currentSort = sort;
      const select = document.getElementById('sort-select') as HTMLSelectElement | null;
      if (select) select.value = sort;
    }
  }

  function getDataAttrName(filterType: string): string {
    if (config.extraDataAttrs && config.extraDataAttrs[filterType]) {
      return config.extraDataAttrs[filterType];
    }
    if (filterType === 'armor-class') return 'armorClass';
    return filterType;
  }

  function updateDisplay() {
    const items = document.querySelectorAll('.item-card');
    let visibleCount = 0;

    items.forEach(item => {
      let visible = true;

      for (const type of config.filterTypes) {
        if (visible && activeFilters[type].size > 0) {
          const el = item as HTMLElement;
          const value = el.dataset[getDataAttrName(type)];
          if (!activeFilters[type].has(value!)) visible = false;
        }
      }

      item.classList.toggle('hidden', !visible);
      if (visible) visibleCount++;
    });

    const filteredCountEl = document.getElementById('filtered-count');
    if (filteredCountEl) filteredCountEl.textContent = visibleCount.toString();

    const noResultsEl = document.getElementById('no-results');
    if (noResultsEl) noResultsEl.classList.toggle('hidden', visibleCount > 0);

    const gridEl = document.getElementById('results-grid');
    if (gridEl) gridEl.classList.toggle('hidden', visibleCount === 0);

    if (visibleCount > 0) sortItems();
    saveStateToUrl();
  }

  function sortItems() {
    const grid = document.getElementById('results-grid')!;
    const items = Array.from(grid.querySelectorAll<HTMLElement>('.item-card:not(.hidden)'));

    items.sort((a, b) => {
      switch (currentSort) {
        case 'name-asc':
          return (a.dataset.name || '').localeCompare(b.dataset.name || '', 'zh-CN');
        case 'name-desc':
          return (b.dataset.name || '').localeCompare(a.dataset.name || '', 'zh-CN');
        case 'tier-asc':
          return parseInt(a.dataset.tier || '0') - parseInt(b.dataset.tier || '0');
        case 'tier-desc':
          return parseInt(b.dataset.tier || '0') - parseInt(a.dataset.tier || '0');
        case 'price-asc':
          return parseInt(a.dataset.price || '0') - parseInt(b.dataset.price || '0');
        case 'price-desc':
          return parseInt(b.dataset.price || '0') - parseInt(a.dataset.price || '0');
        case 'durability-desc':
          return parseInt(b.dataset.durability || '0') - parseInt(a.dataset.durability || '0');
        default:
          return 0;
      }
    });

    items.forEach(item => grid.appendChild(item));
  }

  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const el = chip as HTMLElement;
      const filterType = el.dataset.filterType!;
      const value = el.dataset.value!;

      if (activeFilters[filterType]?.has(value)) {
        activeFilters[filterType].delete(value);
        el.classList.remove('active');
      } else {
        if (!activeFilters[filterType]) {
          activeFilters[filterType] = new Set();
        }
        activeFilters[filterType].add(value);
        el.classList.add('active');
      }

      updateDisplay();
    });
  });

  document.getElementById('clear-filters')?.addEventListener('click', () => {
    for (const key of config.filterTypes) {
      activeFilters[key].clear();
    }

    document.querySelectorAll('.filter-chip').forEach(chip => {
      chip.classList.remove('active');
    });

    updateDisplay();
  });

  document.getElementById('sort-select')?.addEventListener('change', (e) => {
    currentSort = (e.target as HTMLSelectElement).value;
    sortItems();
    saveStateToUrl();
  });

  loadStateFromUrl();
  updateDisplay();
}
