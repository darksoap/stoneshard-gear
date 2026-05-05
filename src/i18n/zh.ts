export const rarityLabels: Record<string, string> = {
  common: '普通',
  unique: '独一无二',
};

export const damageTypeLabels: Record<string, string> = {
  slashing: '劈砍',
  piercing: '穿刺',
  blunt: '钝击',
  rending: '撕裂',
  fire: '灼烧',
  shock: '电击',
  poison: '中毒',
  caustic: '腐蚀',
  frost: '霜冻',
  arcane: '秘术',
  unholy: '邪术',
  sacred: '神圣',
  psionic: '灵能',
};

export const damageTypeColors: Record<string, string> = {
  slashing: '#e8e8e8',
  piercing: '#e8e8e8',
  blunt: '#e8e8e8',
  rending: '#e8e8e8',
  fire: '#ff6b35',
  shock: '#f4d03f',
  poison: '#58af13',
  caustic: '#58af13',
  frost: '#5dade2',
  arcane: '#9973ed',
  unholy: '#a0522d',
  sacred: '#fff6b5',
  psionic: '#8b7ab8',
};

export const slotLabels: Record<string, string> = {
  sword: '单手刀剑',
  axe: '单手斧',
  mace: '单手锤棒',
  dagger: '匕首',
  tool: '工具',
  '2hsword': '双手刀剑',
  '2haxe': '双手斧',
  '2hmace': '双手锤棒',
  '2hstaff': '长杖',
  spear: '长杆刃器',
  bow: '弓',
  crossbow: '弩',
  sling: '投石兵器',
  shield: '盾牌',
  pick: '镐',
  lute: '乐器',
  chain: '锁链',
};

export const weaponSlotSlugs: Record<string, string> = {
  sword: 'swords',
  axe: 'axes',
  mace: 'maces',
  dagger: 'daggers',
  tool: 'tools',
  '2hsword': 'two-handed-swords',
  '2haxe': 'two-handed-axes',
  '2hmace': 'two-handed-maces',
  '2hstaff': 'staves',
  spear: 'spears',
  bow: 'bows',
  crossbow: 'crossbows',
  sling: 'slings',
  shield: 'shields',
  pick: 'pick',
  lute: 'lute',
  chain: 'chain',
};

export const materialLabels: Record<string, string> = {
  metal: '金属',
  wood: '木',
  leather: '皮',
  cloth: '布',
  gem: '宝石',
  gold: '金',
  silver: '银',
};

export const armorClassLabels: Record<string, string> = {
  light: '轻甲',
  medium: '中甲',
  heavy: '重甲',
};

export const tagLabels: Record<string, string> = {
  aldor: '奥尔多',
  nistra: '尼斯特拉',
  skadia: '斯卡迪亚',
  fjall: '弗约',
  elven: '精灵',
  magic: '魔法',
  special: '限定来源',
  unique: '独一无二',
  dungeon: '地下城',
  exc: '初始装备',
  undead: '亡灵',
};

export const propertyLabels: Record<string, string> = {
  accuracy: '准度',
  critChance: '暴击几率',
  critEfficiency: '暴击效果',
  critAvoid: '暴击避免',
  fumbleChance: '失手几率',
  armorPenetration: '护甲穿透',
  armorDamage: '护甲破坏',
  bodypartDamage: '肢体伤害',
  blockPower: '格挡力量',
  blockRecovery: '格挡力量恢复',
  bleedingChance: '出血几率',
  dazeChance: '击晕几率',
  stunChance: '硬直几率',
  knockbackChance: '击退几率',
  immobilizationChance: '限制移动几率',
  staggerChance: '破衡几率',
  maxMana: '精力',
  manaRestoration: '精力自动恢复',
  maxHealth: '生命上限',
  healthRestoration: '生命自动恢复',
  healingReceived: '治疗效果',
  lifesteal: '生命吸取',
  manasteal: '精力吸取',
  abilitiesEnergyCost: '能力精力消耗',
  skillsEnergyCost: '技能精力消耗',
  spellsEnergyCost: '咒法精力消耗',
  cooldownReduction: '冷却时间',
  magicPower: '法力',
  miscastChance: '失误几率',
  miracleChance: '奇观几率',
  miraclePower: '奇观效果',
  bonusRange: '距离加成',
  damageReceived: '所受伤害',
  fatigueGain: '疲劳抗性',
  defense: '防护',
  evasion: '闪躲几率',
  fortitude: '坚忍',
  vision: '视野上限',
  weaponDamage: '兵器伤害',
  damageReturned: '反伤',
  experienceGain: '经验收益',
  blockChance: '格挡几率',
  counterChance: '反击几率',
  energyRestoration: '精力自动恢复',
};

export const resistanceLabels: Record<string, string> = {
  bleeding: '出血抗性',
  knockback: '位移抗性',
  stun: '控制抗性',
  pain: '疼痛抗性',
  physical: '物理抗性',
  nature: '自然抗性',
  magic: '魔法抗性',
  slashing: '劈砍抗性',
  piercing: '穿刺抗性',
  blunt: '钝击抗性',
  rending: '撕裂抗性',
  fire: '灼烧抗性',
  shock: '电击抗性',
  poison: '中毒抗性',
  caustic: '腐蚀抗性',
  frost: '霜冻抗性',
  arcane: '秘术抗性',
  unholy: '邪术抗性',
  sacred: '神圣抗性',
  psionic: '灵能抗性',
};

export const magicPowerLabels: Record<string, string> = {
  pyromantic: '炎术法力',
  geomantic: '地术法力',
  venomantic: '毒术法力',
  electromantic: '电术法力',
  cryomantic: '冰术法力',
  arcanistic: '秘术法力',
  astromantic: '星术法力',
  psimantic: '灵术法力',
};

export const bodyPartLabels: Record<string, string> = {
  head: '头部',
  body: '躯干',
  arms: '上肢',
  legs: '下肢',
};

export const armorSlotLabels: Record<string, string> = {
  head: '头盔',
  chest: '胸甲',
  arms: '手套',
  legs: '靴子',
  waist: '腰带',
  back: '披风',
  shield: '盾牌',
};

export const armorSlotSlugs: Record<string, string> = {
  head: 'helmets',
  chest: 'chests',
  arms: 'gloves',
  legs: 'boots',
  waist: 'belts',
  back: 'cloaks',
  shield: 'shields',
};

export const jewelrySlotLabels: Record<string, string> = {
  ring: '戒指',
  amulet: '护身符',
};

export const jewelrySlotSlugs: Record<string, string> = {
  ring: 'rings',
  amulet: 'amulets',
};
