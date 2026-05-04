import type { CollectionEntry } from "astro:content";

export const base = import.meta.env.BASE_URL.replace(/\/$/, "");

export function withBase(path: string): string {
  return path.startsWith("/") ? `${base}${path}` : path;
}

const TALL_SLOTS = new Set([
  "sword", "axe", "mace", "dagger", "spear", "bow",
  "2hsword", "2haxe", "2hmace", "2hstaff",
]);

const WIDE_SLOTS = new Set(["belt"]);

export function getDetailImgSize(slot: string): { w: string; h: string } {
  if (TALL_SLOTS.has(slot)) return { w: "w-20", h: "h-40" };
  if (WIDE_SLOTS.has(slot)) return { w: "w-40", h: "h-20" };
  return { w: "w-24", h: "h-24" };
}

type AnyItem = CollectionEntry<"weapons"> | CollectionEntry<"armor"> | CollectionEntry<"jewelry">;

interface CategoryInfo {
  slot: string;
  slug: string;
  label: string;
  count: number;
  href?: string;
  sampleImage?: string;
}

function getSlotCounts(items: AnyItem[]): Record<string, number> {
  return items.reduce((acc, item) => {
    acc[item.data.slot] = (acc[item.data.slot] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
}

export function getCategories(
  items: AnyItem[],
  slotSlugs: Record<string, string>,
  slotLabels: Record<string, string>,
  basePath?: string,
): CategoryInfo[] {
  const counts = getSlotCounts(items);
  const base = basePath?.replace(/\/$/, "");

  const firstImageBySlot = items.reduce((acc, item) => {
    if (item.data.image && !acc[item.data.slot]) {
      acc[item.data.slot] = item.data.image;
    }
    return acc;
  }, {} as Record<string, string>);

  return Object.entries(counts)
    .map(([slot, count]) => ({
      slot,
      slug: slotSlugs[slot] || slot,
      label: slotLabels[slot] || slot,
      count,
      href: base ? `${base}/${slotSlugs[slot]}` : undefined,
      sampleImage: firstImageBySlot[slot],
    }))
    .sort((a, b) => b.count - a.count);
}

interface AvailableFilters {
  rarities?: string[];
  tiers?: number[];
  materials?: string[];
  armorClasses?: string[];
}

export function getAvailableFilters(
  items: AnyItem[],
  options?: { includeArmorClass?: boolean },
): AvailableFilters {
  const filters: AvailableFilters = {
    rarities: [...new Set(items.map((i) => i.data.rarity))],
    tiers: [...new Set(items.map((i) => i.data.tier))].sort((a, b) => a - b),
    materials: [...new Set(items.map((i) => i.data.material))],
  };
  if (options?.includeArmorClass) {
    filters.armorClasses = [
      ...new Set(items.map((i) => (i.data as any)["class"])),
    ].filter(Boolean);
  }
  return filters;
}

const NESTED_PROPERTY_KEYS = new Set([
  "resistances",
  "magicPowers",
  "bodyPartProtection",
  "damages",
]);

export function getFilteredProperties(
  props: Record<string, any>,
): Record<string, number> {
  const filtered: Record<string, number> = {};
  for (const [key, value] of Object.entries(props)) {
    if (NESTED_PROPERTY_KEYS.has(key)) continue;
    if (typeof value === "number") {
      filtered[key] = value;
    }
  }
  return filtered;
}


