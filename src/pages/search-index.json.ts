import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { slotLabels, armorSlotLabels } from '../i18n/zh';

export const GET: APIRoute = async () => {
  const weapons = await getCollection('weapons');
  const armor = await getCollection('armor');

  const base = import.meta.env.BASE_URL.replace(/\/$/, '');

  const weaponItems = weapons.map((w) => {
    const slotLabel = slotLabels[w.data.slot] || w.data.slot;
    return {
      id: w.id,
      name: w.data.name,
      nameZh: w.data.nameZh,
      slot: w.data.slot,
      slotLabel,
      tier: w.data.tier,
      rarity: w.data.rarity,
      material: w.data.material,
      collection: 'weapons' as const,
      href: `${base}/weapons/${w.id}`,
    };
  });

  const armorItems = armor.map((a) => {
    const slotLabel = armorSlotLabels[a.data.slot] || a.data.slot;
    return {
      id: a.id,
      name: a.data.name,
      nameZh: a.data.nameZh,
      slot: a.data.slot,
      slotLabel,
      tier: a.data.tier,
      rarity: a.data.rarity,
      material: a.data.material,
      collection: 'armor' as const,
      href: `${base}/armor/${a.id}`,
    };
  });

  const items = [...weaponItems, ...armorItems];

  return new Response(JSON.stringify(items), {
    headers: {
      'Content-Type': 'application/json',
    },
  });
};
