import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import {
    slotLabels,
    armorSlotLabels,
    jewelrySlotLabels,
} from '../i18n/zh';

const slotLabelMap: Record<string, Record<string, string>> = {
    weapons: slotLabels,
    armor: armorSlotLabels,
    jewelry: jewelrySlotLabels,
};

export const GET: APIRoute = async () => {
    const base = import.meta.env.BASE_URL.replace(/\/$/, '');
    const allItems: any[] = [];

    for (const collection of ['weapons', 'armor', 'jewelry'] as const) {
        const items = await getCollection(collection);
        const labels = slotLabelMap[collection];

        for (const item of items) {
            const slotLabel = labels[item.data.slot] || item.data.slot;
            allItems.push({
                id: item.id,
                name: item.data.name,
                nameZh: item.data.nameZh,
                slot: item.data.slot,
                slotLabel,
                tier: item.data.tier,
                rarity: item.data.rarity,
                material: item.data.material,
                image: item.data.image,
                collection,
                href: `${base}/${collection}/${item.id}`,
            });
        }
    }

    return new Response(JSON.stringify(allItems), {
        headers: {
            'Content-Type': 'application/json',
        },
    });
};
