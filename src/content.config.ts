import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const RarityEnum = z.enum(['common', 'unique']);
const MaterialEnum = z.enum(['cloth', 'gem', 'gold', 'leather', 'metal', 'silver', 'wood']);
const ArmorClassEnum = z.enum(['light', 'medium', 'heavy']);
const DamageTypeEnum = z.enum(['slashing', 'piercing', 'blunt', 'rending', 'fire', 'shock', 'poison', 'caustic', 'frost', 'arcane', 'unholy', 'sacred', 'psionic']);
const TagEnum = z.enum(['aldor', 'elven', 'fjall', 'nistra', 'special', 'unique', 'dungeon', 'exc', 'magic', 'undead', 'skadia']);

const WeaponSlotEnum = z.enum([
  'sword',
  'axe',
  'mace',
  'dagger',
  '2hsword',
  '2haxe',
  '2hmace',
  '2hstaff',
  'spear',
  'bow',
  'crossbow',
  'sling',
  'tool',
  'pick',
  'lute',
  'chain',
]);

const ArmorSlotEnum = z.enum([
  'head',
  'chest',
  'arms',
  'legs',
  'waist',
  'back',
  'shield',
]);

const JewelrySlotEnum = z.enum([
  'ring',
  'amulet',
]);

const ResistanceSchema = z.record(z.string(), z.number());
const MagicPowerSchema = z.record(z.string(), z.number());
const BodyPartProtectionSchema = z.record(z.string(), z.number());
const DamagesSchema = z.record(z.string(), z.number());

const NumericPropertySchema = z.number();

const PropertiesSchema = z.object({
  accuracy: NumericPropertySchema.optional(),
  critChance: NumericPropertySchema.optional(),
  critEfficiency: NumericPropertySchema.optional(),
  critAvoid: NumericPropertySchema.optional(),
  fumbleChance: NumericPropertySchema.optional(),
  armorPenetration: NumericPropertySchema.optional(),
  armorDamage: NumericPropertySchema.optional(),
  bodypartDamage: NumericPropertySchema.optional(),
  weaponDamage: NumericPropertySchema.optional(),
  damageReturned: NumericPropertySchema.optional(),
  blockPower: NumericPropertySchema.optional(),
  blockRecovery: NumericPropertySchema.optional(),
  blockChance: NumericPropertySchema.optional(),
  counterChance: NumericPropertySchema.optional(),
  evasion: NumericPropertySchema.optional(),
  defense: NumericPropertySchema.optional(),
  fortitude: NumericPropertySchema.optional(),
  vision: NumericPropertySchema.optional(),
  bonusRange: NumericPropertySchema.optional(),
  maxMana: NumericPropertySchema.optional(),
  manaRestoration: NumericPropertySchema.optional(),
  energyRestoration: NumericPropertySchema.optional(),
  maxHealth: NumericPropertySchema.optional(),
  healthRestoration: NumericPropertySchema.optional(),
  healingReceived: NumericPropertySchema.optional(),
  lifesteal: NumericPropertySchema.optional(),
  manasteal: NumericPropertySchema.optional(),
  abilitiesEnergyCost: NumericPropertySchema.optional(),
  skillsEnergyCost: NumericPropertySchema.optional(),
  spellsEnergyCost: NumericPropertySchema.optional(),
  cooldownReduction: NumericPropertySchema.optional(),
  magicPower: NumericPropertySchema.optional(),
  miscastChance: NumericPropertySchema.optional(),
  miracleChance: NumericPropertySchema.optional(),
  miraclePower: NumericPropertySchema.optional(),
  damageReceived: NumericPropertySchema.optional(),
  fatigueGain: NumericPropertySchema.optional(),
  experienceGain: NumericPropertySchema.optional(),
  bleedingChance: NumericPropertySchema.optional(),
  dazeChance: NumericPropertySchema.optional(),
  stunChance: NumericPropertySchema.optional(),
  staggerChance: NumericPropertySchema.optional(),
  knockbackChance: NumericPropertySchema.optional(),
  immobilizationChance: NumericPropertySchema.optional(),
  resistances: ResistanceSchema.optional(),
  magicPowers: MagicPowerSchema.optional(),
  bodyPartProtection: BodyPartProtectionSchema.optional(),
  damages: DamagesSchema.optional(),
}).catchall(NumericPropertySchema);

const baseItemSchema = z.object({
  id: z.string(),
  name: z.string(),
  nameZh: z.string(),
  tier: z.number().int().min(1).max(5),
  material: MaterialEnum,
  rarity: RarityEnum,
  version: z.string().default('0.9.4.20'),
  properties: PropertiesSchema,
  durability: z.number().int().nonnegative(),
  price: z.number().int().nonnegative(),
  image: z.string(),
});

const variantSchema = z.object({
  id: z.string(),
  name: z.string(),
  nameZh: z.string(),
  image: z.string().optional(),
  durability: z.number().int().nonnegative().optional(),
  properties: PropertiesSchema,
  tags: z.array(TagEnum).optional(),
});

const weaponSchema = baseItemSchema.extend({
  slot: WeaponSlotEnum,
  damage: z.object({
    value: z.number(),
    type: DamageTypeEnum,
  }).optional(),
  range: z.number().int().nonnegative().optional(),
  class: ArmorClassEnum.optional(),
  tags: z.array(TagEnum).optional(),
  description: z.string().optional(),
  descriptionZh: z.string().optional(),
  variant: variantSchema.optional(),
});

const armorSchema = baseItemSchema.extend({
  slot: ArmorSlotEnum,
  class: ArmorClassEnum,
  tags: z.array(TagEnum).optional(),
  fireproof: z.boolean().optional(),
  description: z.string().optional(),
  descriptionZh: z.string().optional(),
  variant: variantSchema.optional(),
});

const jewelrySchema = baseItemSchema.extend({
  slot: JewelrySlotEnum,
  tags: z.array(TagEnum).optional(),
  description: z.string().optional(),
  descriptionZh: z.string().optional(),
  variant: variantSchema.optional(),
});

const weapons = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/weapons' }),
  schema: weaponSchema,
});

const armor = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/armor' }),
  schema: armorSchema,
});

const jewelry = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/jewelry' }),
  schema: jewelrySchema,
});

export const collections = {
  weapons,
  armor,
  jewelry,
};
