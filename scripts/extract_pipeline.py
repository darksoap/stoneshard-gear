#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紫色晶石游戏装备数据提取 Pipeline
- 从 data.win 解包到 JSON 输出
- 合并 items_stats 中的额外属性
- 按 slot 分类存放文件
- 重甲头盔变种合并
- 自动从游戏文件提取版本号
- 支持单独运行某个阶段
"""

import argparse
import csv
import json
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from PIL import Image


# ============================================================================
# 配置与日志
# ============================================================================
@dataclass
class Config:
    game_data: Path
    unpacked_dir: Path
    extracted_dir: Path
    json_dir: Path
    utmt_cli: Path
    strings_dump: Path
    sprites_dump: Path = Path("/tmp/sprites_dump")
    version: str = "modbrunch"
    step_spec: str = None


class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'


def log_step(step_num: int, total: int, message: str):
    print(f"\n{Colors.BLUE}[{step_num}/{total}]{Colors.END} {message}")


def log_success(message: str):
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def log_error(message: str):
    print(f"{Colors.RED}✗{Colors.END} {message}")


def log_info(message: str):
    print(f"{Colors.YELLOW}ℹ{Colors.END} {message}")


# ============================================================================
# GML 解析工具
# ============================================================================
def parse_gml_string_array(content: str) -> Optional[List[str]]:
    """从 GML 内容中提取 return [...] 内的引号字符串列表"""
    match = re.search(r'return\s*\[([\s\S]*?)\];\s*}', content)
    if not match:
        return None

    array_content = match.group(1)
    items = []
    i = 0
    while i < len(array_content):
        while i < len(array_content) and array_content[i] in ' \t\n\r,':
            i += 1
        if i >= len(array_content):
            break
        if array_content[i] == '"':
            j = i + 1
            while j < len(array_content):
                if array_content[j] == '\\' and j + 1 < len(array_content):
                    j += 2
                elif array_content[j] == '"':
                    break
                else:
                    j += 1
            items.append(array_content[i + 1:j])
            i = j + 1
        else:
            i += 1
    return items if items else None


def parse_gml_table(file_path: Path) -> Optional[Dict[str, Any]]:
    """解析 GML 文件中的 table 数据，返回 {headers, rows, count}"""
    content = file_path.read_text(encoding='utf-8', errors='ignore')
    items = parse_gml_string_array(content)
    if not items:
        return None

    headers = items[0].split(';')
    rows = []
    for line in items[1:]:
        if line.startswith('//') or line.startswith('[') or not line.strip():
            continue
        row = line.split(';')
        if row and any(cell.strip() for cell in row):
            rows.append(row)

    return {'headers': headers, 'rows': rows, 'count': len(rows)}


# ============================================================================
# 版本提取与参数解析
# ============================================================================
def extract_version_from_game(game_data: Path, utmt_cli: Path) -> Optional[str]:
    temp_dir = Path("/tmp/version_extract")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    try:
        subprocess.run(
            [str(utmt_cli), "dump", str(game_data),
             "-c", "gml_GlobalScript_scr_debug_get_source_hash",
             "-o", str(temp_dir)],
            capture_output=True, text=True, timeout=60
        )

        version_file = temp_dir / "CodeEntries" / "gml_GlobalScript_scr_debug_get_source_hash.gml"
        if version_file.exists():
            content = version_file.read_text(encoding='utf-8', errors='ignore')
            match = re.search(r'_message\s*=\s*"([^"]+)"', content)
            if match:
                version = re.sub(r'-vm$', '', match.group(1))
                shutil.rmtree(temp_dir)
                return version
            match = re.search(r'_versionString\s*=\s*"([\d.]+)', content)
            if match:
                shutil.rmtree(temp_dir)
                return match.group(1)

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception:
        pass
    return None


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="游戏装备数据提取 Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s data.win
  %(prog)s data.win -o json_output
  %(prog)s data.win -s json          只运行 JSON 转换
  %(prog)s data.win -s 3,5           运行步骤 3 和 5
  %(prog)s data.win -s 2-4           运行步骤 2 到 4
        """
    )

    parser.add_argument("game_data", type=Path, help="游戏数据文件路径 (data.win)")
    parser.add_argument("-o", "--output", type=Path, default=Path("json_output"),
                        help="JSON 输出目录 (默认: json_output)")
    parser.add_argument("-u", "--utmt", type=Path,
                        default=Path.home() / "UTMT" / "UndertaleModCli",
                        help="UndertaleModCli 工具路径")
    parser.add_argument("--unpacked", type=Path, default=None,
                        help="解包文件存放目录")
    parser.add_argument("--tables", type=Path, default=None,
                        help="CSV 表格存放目录")
    parser.add_argument("--strings", type=Path,
                        default=Path("/tmp/strings_dump/strings.txt"),
                        help="字符串转储文件路径")
    parser.add_argument("--version", type=str, default=None,
                        help="游戏版本号 (默认: 自动提取)")
    parser.add_argument("-s", "--step", type=str, default=None,
                        help="只运行指定阶段 (1-5 或名称: unpack,strings,tables,sprites,json)")

    args = parser.parse_args()
    game_data = args.game_data.resolve()
    base_dir = game_data.parent

    version = args.version
    if version is None:
        version = extract_version_from_game(game_data, args.utmt) or "0.9.4.18"

    return Config(
        game_data=game_data,
        unpacked_dir=args.unpacked or base_dir / "unpacked",
        extracted_dir=args.tables or base_dir / "extracted_tables",
        json_dir=args.output.resolve(),
        utmt_cli=args.utmt,
        strings_dump=args.strings,
        version=version,
        step_spec=args.step,
    )


# ============================================================================
# Step 1: 解包 data.win
# ============================================================================
TABLES_TO_EXTRACT = [
    "gml_GlobalScript_table_weapons",
    "gml_GlobalScript_table_armor",
    "gml_GlobalScript_table_equipment",
    "gml_GlobalScript_table_items",
    "gml_GlobalScript_table_items_stats",
    "gml_GlobalScript_table_attributes",
    "gml_GlobalScript_table_mobs",
    "gml_GlobalScript_table_mobs_stats",
    "gml_GlobalScript_table_skills",
    "gml_GlobalScript_table_drops",
]


def step1_unpack(cfg: Config) -> bool:
    log_step(1, 5, "解包 data.win 文件")

    if not cfg.game_data.exists():
        log_error(f"找不到游戏数据文件: {cfg.game_data}")
        return False
    if not cfg.utmt_cli.exists():
        log_error(f"找不到解包工具: {cfg.utmt_cli}")
        return False

    if cfg.unpacked_dir.exists():
        key_files = ['table_weapons', 'table_armor', 'table_equipment', 'table_attributes']
        if all(any(cfg.unpacked_dir.glob(f"*{f}*.gml")) for f in key_files):
            log_info("检测到已有完整解包数据，跳过解包步骤")
            gml_files = list(cfg.unpacked_dir.glob("*.gml"))
            log_success(f"使用现有 {len(gml_files)} 个 GML 文件")
            return True

    if cfg.unpacked_dir.exists():
        shutil.rmtree(cfg.unpacked_dir)
    cfg.unpacked_dir.mkdir(parents=True, exist_ok=True)

    log_info("解包需要较长时间，请耐心等待...")

    extracted_count = 0
    temp_dir = Path("/tmp/t")
    for table in TABLES_TO_EXTRACT:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            subprocess.run(
                [str(cfg.utmt_cli), "dump", str(cfg.game_data), "-c", table, "-o", "/tmp/t"],
                capture_output=True, text=True, timeout=60
            )
            code_entries = temp_dir / "CodeEntries"
            if code_entries.exists():
                for gml_file in code_entries.glob("*.gml"):
                    shutil.copy2(gml_file, cfg.unpacked_dir / gml_file.name)
                    extracted_count += 1
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except Exception as e:
            log_error(f"提取 {table} 出错: {e}")

    if extracted_count > 0:
        log_success(f"提取了 {extracted_count} 个关键 GML 文件")
        return True
    log_error("未能提取任何 GML 文件")
    return False


# ============================================================================
# Step 2: 提取字符串资源
# ============================================================================
def step2_extract_strings(cfg: Config) -> bool:
    log_step(2, 5, "提取字符串资源")

    strings_dir = Path("/tmp/strings_dump")
    if strings_dir.exists():
        shutil.rmtree(strings_dir)

    try:
        subprocess.run(
            [str(cfg.utmt_cli), "dump", str(cfg.game_data), "-s", "-o", str(strings_dir)],
            capture_output=True, text=True, timeout=120
        )
        if cfg.strings_dump.exists():
            size = cfg.strings_dump.stat().st_size / (1024 * 1024)
            log_success(f"字符串提取完成，大小: {size:.1f} MB")
            return True
        log_error("字符串文件未生成")
        return False
    except Exception as e:
        log_error(f"提取字符串出错: {e}")
        return False


# ============================================================================
# Step 3: 解析 GML Table 为 CSV
# ============================================================================
GML_TABLE_FILES = [
    ("weapons", "gml_GlobalScript_table_weapons.gml"),
    ("armor", "gml_GlobalScript_table_armor.gml"),
    ("equipment", "gml_GlobalScript_table_equipment.gml"),
    ("items", "gml_GlobalScript_table_items.gml"),
    ("items_stats", "gml_GlobalScript_table_items_stats.gml"),
    ("attributes", "gml_GlobalScript_table_attributes.gml"),
    ("mobs", "gml_GlobalScript_table_mobs.gml"),
    ("mobs_stats", "gml_GlobalScript_table_mobs_stats.gml"),
]


def step3_extract_tables(cfg: Config) -> bool:
    log_step(3, 5, "提取 Table 数据为 CSV")

    if cfg.extracted_dir.exists():
        shutil.rmtree(cfg.extracted_dir)
    cfg.extracted_dir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    for name, filename in GML_TABLE_FILES:
        file_path = cfg.unpacked_dir / filename
        if not file_path.exists():
            continue
        data = parse_gml_table(file_path)
        if data and data['rows']:
            with open(cfg.extracted_dir / f"{name}.csv", 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerows([data['headers']] + data['rows'])
            extracted += 1

    log_success(f"提取了 {extracted} 个 table 文件")
    return extracted > 0


# ============================================================================
# Step 4: 提取 Sprite 图片
# ============================================================================
def step4_extract_sprites(cfg: Config) -> bool:
    log_step(4, 5, "提取物品 Sprite 图片")

    sprites_dir = cfg.sprites_dump
    if sprites_dir.exists():
        shutil.rmtree(sprites_dir)

    if not cfg.game_data.exists() or not cfg.utmt_cli.exists():
        log_error("缺少游戏数据或解包工具")
        return False

    csx_script = Path("/tmp/export_inv_sprites.csx")
    csx_content = '''using System.Text;
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using UndertaleModLib.Util;

EnsureDataLoaded();

string texFolder = "SPRITES_OUTPUT_DIR";
if (!Directory.Exists(texFolder))
    Directory.CreateDirectory(texFolder);

TextureWorker worker = null;
using (worker = new())
{
    int count = 0;
    foreach (var sprite in Data.Sprites)
    {
        if (sprite is null) continue;
        if (sprite.Name.Content.StartsWith("s_inv_"))
        {
            for (int i = 0; i < sprite.Textures.Count; i++)
            {
                if (sprite.Textures[i]?.Texture is not null)
                {
                    string path = Path.Combine(texFolder, $"{sprite.Name.Content}_{i}.png");
                    worker.ExportAsPNG(sprite.Textures[i].Texture, path, null, false);
                    count++;
                }
            }
        }
    }
    ScriptMessage($"Exported {count} inventory sprite textures.");
}
'''.replace("SPRITES_OUTPUT_DIR", str(sprites_dir.resolve()))
    csx_script.write_text(csx_content, encoding='utf-8')

    log_info("提取 sprite 图片（可能需要几分钟）...")

    try:
        subprocess.run(
            [str(cfg.utmt_cli), "load", str(cfg.game_data), "-s", str(csx_script)],
            capture_output=True, text=True, timeout=300
        )
        png_count = len(list(sprites_dir.glob("*.png"))) if sprites_dir.exists() else 0
        if png_count > 0:
            log_success(f"提取了 {png_count} 个 sprite 图片")
            return True
        log_error("未能提取任何 sprite 图片")
        return False
    except subprocess.TimeoutExpired:
        log_error("sprite 提取超时")
        return False
    except Exception as e:
        log_error(f"sprite 提取出错: {e}")
        return False


# ============================================================================
# 数据加载工具
# ============================================================================
def safe_int(value: str, default: int = 0) -> int:
    if not value or value.strip() == '':
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value: str, default: float = 0.0) -> float:
    if not value or value.strip() == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def to_kebab_case(name: str) -> str:
    name = re.sub(r'[^\w\s]', ' ', name)
    words = name.split()
    return '-'.join(word.lower() for word in words if word)


def _extract_short_name(text: str) -> str:
    if not text:
        return ''
    if len(text) <= 40 and '##' not in text:
        return text
    for sep in ['##', '.#', '.']:
        idx = text.find(sep)
        if idx > 0:
            candidate = text[:idx].strip()
            if candidate:
                return candidate
    return text[:40].strip()


def load_items_stats(cfg: Config) -> Dict[str, Dict[str, str]]:
    stats_file = cfg.extracted_dir / "items_stats.csv"
    if not stats_file.exists():
        return {}
    stats_map = {}
    with open(stats_file, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            item_id = row.get('id', '').strip()
            if item_id:
                stats_map[item_id.lower()] = row
    return stats_map


def parse_translations(cfg: Config) -> Tuple[Dict[str, str], Dict[str, Tuple[str, str]]]:
    """解析名称翻译和描述。策略：同一 key 多行时，en 最短为名称，最长为描述"""
    name_map = {}
    desc_map = {}

    if not cfg.strings_dump.exists():
        return name_map, desc_map

    content = cfg.strings_dump.read_text(encoding='utf-8', errors='ignore')
    key_lines = defaultdict(list)
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 4:
            continue
        item_name = parts[0].strip()
        english = parts[2].strip() if len(parts) > 2 else ''
        chinese = parts[3].strip() if len(parts) > 3 else ''
        if not item_name or item_name.startswith('//'):
            continue
        if not english or not any('\u4e00' <= c <= '\u9fff' for c in chinese):
            continue
        key_lines[item_name.lower()].append((english, chinese))

    for key, lines in key_lines.items():
        if len(lines) == 1:
            en, zh = lines[0]
            if len(en) <= 50 and len(zh) <= 50 and '.' not in en:
                name_map[key] = zh
            else:
                desc_map[key] = (en, zh)
        else:
            sorted_lines = sorted(lines, key=lambda x: len(x[0]))
            name_en, name_zh = sorted_lines[0]
            desc_en, desc_zh = sorted_lines[-1]
            if len(name_en) <= 50 and len(name_zh) <= 50:
                name_map[key] = name_zh
            if len(desc_en) > 30 or '.' in desc_en:
                desc_map[key] = (desc_en, desc_zh)

    return name_map, desc_map


def load_attributes_terminology(cfg: Config) -> Dict[str, Dict[str, str]]:
    """从 table_attributes.gml 加载官方术语映射，只取 // TRADE STATS 之前的战斗属性"""
    gml_file = cfg.unpacked_dir / "gml_GlobalScript_table_attributes.gml"
    if not gml_file.exists():
        return {}

    content = gml_file.read_text(encoding='utf-8', errors='ignore')
    items = parse_gml_string_array(content)
    if not items:
        return {}

    terminology = {}
    for item in items[2:]:
        parts = item.split(';')
        if len(parts) < 4:
            continue
        key = parts[0].strip()
        en = parts[2].strip()
        zh = parts[3].strip()
        if en.startswith('// TRADE STATS') or zh.startswith('// TRADE STATS'):
            break
        if key and not key.startswith('//') and (en or zh):
            en_short = _extract_short_name(en)
            zh_short = _extract_short_name(zh)
            entry = {'nameEn': en_short, 'nameZh': zh_short}
            if en != en_short:
                entry['descEn'] = en
            if zh != zh_short:
                entry['descZh'] = zh
            terminology[key] = entry

    return terminology


# ============================================================================
# 属性映射与提取
# ============================================================================
COMBAT_PROPS = {
    'Hit_Chance': 'accuracy',
    'CRT': 'critChance',
    'CRTD': 'critEfficiency',
    'CTA': 'critAvoid',
    'FMB': 'fumbleChance',
    'Armor_Piercing': 'armorPenetration',
    'Armor_Damage': 'armorDamage',
    'Bodypart_Damage': 'bodypartDamage',
    'PRR': 'damageReduction',
    'Block_Power': 'blockPower',
    'Block_Recovery': 'blockRecovery',
    'Bleeding_Chance': 'bleedingChance',
    'Daze_Chance': 'dazeChance',
    'Stun_Chance': 'stunChance',
    'Knockback_Chance': 'knockbackChance',
    'Immob_Chance': 'immobilizationChance',
    'Stagger_Chance': 'staggerChance',
    'MP': 'maxMana',
    'MP_Restoration': 'manaRestoration',
    'max_hp': 'maxHealth',
    'Health_Restoration': 'healthRestoration',
    'Healing_Received': 'healingReceived',
    'Lifesteal': 'lifesteal',
    'Manasteal': 'manasteal',
    'Abilities_Energy_Cost': 'abilitiesEnergyCost',
    'Skills_Energy_Cost': 'skillsEnergyCost',
    'Spells_Energy_Cost': 'spellsEnergyCost',
    'Cooldown_Reduction': 'cooldownReduction',
    'Magic_Power': 'magicPower',
    'Miscast_Chance': 'miscastChance',
    'Miracle_Chance': 'miracleChance',
    'Miracle_Power': 'miraclePower',
    'Bonus_Range': 'bonusRange',
    'Damage_Received': 'damageReceived',
    'Fatigue_Gain': 'fatigueGain',
}

ARMOR_ONLY_PROPS = {
    'DEF': 'defense',
    'EVS': 'evasion',
    'Crit_Avoid': 'critAvoid',
    'Fortitude': 'fortitude',
    'VSN': 'vision',
    'Weapon_Damage': 'weaponDamage',
    'Damage_Returned': 'damageReturned',
}

RESISTANCE_MAP = {
    'Bleeding_Resistance': 'bleeding',
    'Knockback_Resistance': 'knockback',
    'Stun_Resistance': 'stun',
    'Pain_Resistance': 'pain',
    'Physical_Resistance': 'physical',
    'Nature_Resistance': 'nature',
    'Magic_Resistance': 'magic',
    'Slashing_Resistance': 'slashing',
    'Piercing_Resistance': 'piercing',
    'Blunt_Resistance': 'blunt',
    'Rending_Resistance': 'rending',
    'Fire_Resistance': 'fire',
    'Shock_Resistance': 'shock',
    'Poison_Resistance': 'poison',
    'Caustic_Resistance': 'caustic',
    'Frost_Resistance': 'frost',
    'Arcane_Resistance': 'arcane',
    'Unholy_Resistance': 'unholy',
    'Sacred_Resistance': 'sacred',
    'Psionic_Resistance': 'psionic',
}

MAGIC_POWER_MAP = {
    'Pyromantic_Power': 'pyromantic',
    'Geomantic_Power': 'geomantic',
    'Venomantic_Power': 'venomantic',
    'Electromantic_Power': 'electromantic',
    'Cryomantic_Power': 'cryomantic',
    'Arcanistic_Power': 'arcanistic',
    'Astromantic_Power': 'astromantic',
    'Psimantic_Power': 'psimantic',
}

DAMAGE_FIELDS = [
    ('Slashing_Damage', 'slashing'),
    ('Piercing_Damage', 'piercing'),
    ('Blunt_Damage', 'blunt'),
    ('Rending_Damage', 'rending'),
    ('Fire_Damage', 'fire'),
    ('Shock_Damage', 'shock'),
    ('Poison_Damage', 'poison'),
    ('Caustic_Damage', 'caustic'),
    ('Frost_Damage', 'frost'),
    ('Arcane_Damage', 'arcane'),
    ('Unholy_Damage', 'unholy'),
    ('Sacred_Damage', 'sacred'),
    ('Psionic_Damage', 'psionic'),
]

BODY_PART_FIELDS = [
    ('Head_DEF', 'head'),
    ('Body_DEF', 'body'),
    ('Arms_DEF', 'arms'),
    ('Legs_DEF', 'legs'),
]

ALL_PROP_MAPPINGS = [COMBAT_PROPS, ARMOR_ONLY_PROPS, RESISTANCE_MAP, MAGIC_POWER_MAP]

CSV_TO_JSON_KEY = {}
for mapping in ALL_PROP_MAPPINGS:
    CSV_TO_JSON_KEY.update(mapping)
for field, dtype in DAMAGE_FIELDS:
    CSV_TO_JSON_KEY[field] = dtype
for field, pname in BODY_PART_FIELDS:
    CSV_TO_JSON_KEY[field] = pname


def extract_props(row: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, int]:
    return {json_field: val for csv_field, json_field in mapping.items()
            if (val := safe_int(row.get(csv_field, ''), 0)) != 0}


def extract_damages(row: Dict[str, str]) -> Tuple[Dict[str, int], str, int]:
    damages = {}
    primary_type = 'slashing'
    primary_value = 0
    for field, dtype in DAMAGE_FIELDS:
        val = safe_int(row.get(field, ''), 0)
        if val > 0:
            damages[dtype] = val
            if val > primary_value:
                primary_type = dtype
                primary_value = val
    return damages, primary_type, primary_value


def extract_body_parts(row: Dict[str, str]) -> Dict[str, int]:
    return {pname: val for field, pname in BODY_PART_FIELDS
            if (val := safe_int(row.get(field, ''), 0)) > 0}


# ============================================================================
# 装备转换
# ============================================================================
SLOT_FOLDER_MAP = {
    'sword': 'swords', 'axe': 'axes', 'mace': 'maces', 'dagger': 'daggers',
    '2hsword': 'two-handed-swords', '2haxe': 'two-handed-axes', '2hmace': 'two-handed-maces',
    '2hStaff': 'staves', 'spear': 'spears', 'bow': 'bows', 'crossbow': 'crossbows',
    'sling': 'slings', 'shield': 'shields',
    'Head': 'helmets', 'Chest': 'chests', 'Arms': 'gloves', 'Legs': 'boots',
    'Waist': 'belts', 'Ring': 'rings', 'Amulet': 'amulets', 'Back': 'cloaks',
}

VALID_TAGS = {'aldor', 'elven', 'fjall', 'nistra', 'special', 'unique',
              'dungeon', 'exc', 'magic', 'undead'}


def get_slot_folder(slot: str) -> str:
    return SLOT_FOLDER_MAP.get(slot, slot.lower())


def parse_tags(tags_str: str) -> List[str]:
    if not tags_str:
        return []
    seen = set()
    result = []
    for tag in tags_str.split():
        tag = tag.strip().lower()
        if tag in VALID_TAGS and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def find_translations(name: str, name_map: Dict[str, str],
                      desc_map: Dict[str, Tuple[str, str]]) -> Tuple[str, str, str]:
    """查找名称和描述的翻译，返回 (zh_name, en_desc, zh_desc)"""
    key = name.lower()
    zh_name = name_map.get(key, '')
    en_desc, zh_desc = desc_map.get(key, ('', ''))

    alt_keys = []
    if "'s" in name:
        alt_keys.append(name.replace("'s", "").strip().lower())
    else:
        words = name.split()
        if len(words) > 1:
            alt_keys.append((" ".join(words[:-1]) + "'s " + words[-1]).lower())
    if name.startswith("Open "):
        alt_keys.append(name[5:].lower())

    for alt_key in alt_keys:
        if not zh_name:
            zh_name = name_map.get(alt_key, '')
        if not en_desc:
            en_desc, zh_desc = desc_map.get(alt_key, ('', ''))
        if zh_name and en_desc:
            break

    return zh_name, en_desc, zh_desc


def _build_base_data(row: Dict[str, str], category: str,
                     name_map: Dict[str, str], desc_map: Dict[str, Tuple[str, str]],
                     properties: Dict) -> Tuple[Dict, str, str]:
    """构建武器/护甲共用的基础数据字典，返回 (data, slot_folder, file_name)"""
    name = row.get('name', '').strip()
    file_name = to_kebab_case(name)
    slot = row.get('Slot', '').strip()
    slot_folder = get_slot_folder(slot)
    zh_name, en_desc, zh_desc = find_translations(name, name_map, desc_map)
    tags = parse_tags(row.get('tags', ''))

    data = {
        "id": file_name,
        "name": name,
        "nameZh": zh_name,
        "slot": slot.lower(),
        "tier": safe_int(row.get('Tier', ''), 1),
        "rarity": row.get('rarity', 'Common').lower(),
        "material": row.get('Mat', 'metal').lower(),
        "image": f"/images/{category}/{slot_folder}/{file_name}.webp",
        "durability": safe_int(row.get('MaxDuration', ''), 100),
        "price": safe_int(row.get('Price', ''), 0),
        "properties": properties,
    }

    if tags:
        data["tags"] = tags
    if en_desc:
        data["description"] = en_desc
    if zh_desc:
        data["descriptionZh"] = zh_desc

    return data, slot_folder, file_name


def convert_weapon(row: Dict[str, str], name_map: Dict[str, str],
                   desc_map: Dict[str, Tuple[str, str]],
                   stats_map: Dict[str, Dict[str, str]],
                   cfg: Config) -> Optional[Tuple[Dict, str, str]]:
    name = row.get('name', '').strip()
    if not name:
        return None

    item_id = row.get('id', '').strip()
    properties = extract_props(row, COMBAT_PROPS)

    if item_id and item_id.lower() in stats_map:
        stats_row = stats_map[item_id.lower()]
        resistances = extract_props(stats_row, RESISTANCE_MAP)
        if resistances:
            properties['resistances'] = resistances
        properties.update(extract_props(stats_row, {
            'Received_XP': 'experienceGain',
            'VSN': 'vision',
            'Fortitude': 'fortitude',
        }))

    damages, primary_type, primary_value = extract_damages(row)
    if len(damages) > 1:
        properties['damages'] = damages
    magic_powers = extract_props(row, MAGIC_POWER_MAP)
    if magic_powers:
        properties['magicPowers'] = magic_powers

    data, slot_folder, file_name = _build_base_data(row, 'weapons', name_map, desc_map, properties)

    data["damage"] = {"value": primary_value, "type": primary_type}
    range_val = safe_int(row.get('Rng', ''), 0)
    if range_val > 0:
        data["range"] = range_val

    return data, slot_folder, file_name


def convert_armor(row: Dict[str, str], name_map: Dict[str, str],
                  desc_map: Dict[str, Tuple[str, str]],
                  stats_map: Dict[str, Dict[str, str]],
                  cfg: Config) -> Optional[Tuple[Dict, str, str]]:
    name = row.get('name', '').strip()
    if not name:
        return None

    item_id = row.get('id', '').strip()
    armor_class = row.get('class', '').strip()

    all_prop_mapping = {**COMBAT_PROPS, **ARMOR_ONLY_PROPS}
    properties = extract_props(row, all_prop_mapping)

    resistances = extract_props(row, RESISTANCE_MAP)
    if item_id and item_id.lower() in stats_map:
        stats_row = stats_map[item_id.lower()]
        for json_field, val in extract_props(stats_row, RESISTANCE_MAP).items():
            if json_field not in resistances:
                resistances[json_field] = val
        for k, v in extract_props(stats_row, {
            'Received_XP': 'experienceGain',
            'Fatigue_Gain': 'fatigueGain',
        }).items():
            if k not in properties:
                properties[k] = v

    if resistances:
        properties['resistances'] = resistances
    magic_powers = extract_props(row, MAGIC_POWER_MAP)
    if magic_powers:
        properties['magicPowers'] = magic_powers
    body_parts = extract_body_parts(row)
    if body_parts:
        properties['bodyPartProtection'] = body_parts

    data, slot_folder, file_name = _build_base_data(row, 'armor', name_map, desc_map, properties)

    data["class"] = armor_class.lower() if armor_class else ""
    if row.get('fireproof', '').strip() == '1':
        data["fireproof"] = True

    return data, slot_folder, file_name


# ============================================================================
# 变种检测
# ============================================================================
def build_variant_map(armor_rows: List[Dict[str, str]]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """构建变种映射，返回 (variant_of, base_of)
    
    variant_of: {变种名 → 基础名}
    base_of:    {基础名 → 变种名}
    仅处理 class=heavy 且有 visorSwitch 的重甲头盔
    """
    variant_of = {}
    for row in armor_rows:
        visor = row.get('visorSwitch', '').strip()
        name = row.get('name', '').strip()
        armor_class = row.get('class', '').strip().lower()
        if not visor or armor_class != 'heavy':
            continue
        if name.startswith('Open '):
            base_name = name[5:]
            if base_name not in variant_of:
                variant_of[name] = base_name
        else:
            variant_of[visor] = name

    base_of = {}
    for vname, bname in variant_of.items():
        base_of[bname] = vname

    return variant_of, base_of


# ============================================================================
# Sprite 图片处理
# ============================================================================
def build_sprite_map(sprites_dir: Path) -> Dict[str, Path]:
    """构建 sprite 基础名到文件路径的映射"""
    sprite_map = {}
    if not sprites_dir.exists():
        return sprite_map
    for png_file in sorted(sprites_dir.glob("s_inv_*_0.png")):
        sprite_name = re.sub(r'_0$', '', re.sub(r'^s_inv_', '', png_file.stem))
        sprite_map[sprite_name.lower()] = png_file
    return sprite_map


def name_to_sprite_key(name: str) -> str:
    key = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    key = re.sub(r'^open', '', key)
    return key


def export_sprite_images(cfg: Config, sprite_map: Dict[str, Path]) -> int:
    """将 sprite 图片转为 webp 并输出到 public/images/，同时更新 JSON 中的 image 字段。
    返回导出数量"""
    public_dir = cfg.json_dir.parent / "public"
    images_dir = public_dir / "images"
    if images_dir.exists():
        shutil.rmtree(images_dir)

    exported = 0
    for json_file in cfg.json_dir.rglob("*.json"):
        if json_file.name in ("index.json",):
            continue
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        name = data.get("name", "")
        item_id = data.get("id", "")
        if not name or not item_id:
            continue

        sprite_key = name_to_sprite_key(name)
        if sprite_key not in sprite_map:
            continue

        src_png = sprite_map[sprite_key]
        rel = json_file.relative_to(cfg.json_dir)
        parts = list(rel.parts)
        parts[-1] = f"{item_id}.webp"
        dest_webp = images_dir / Path(*parts)
        dest_webp.parent.mkdir(parents=True, exist_ok=True)

        try:
            Image.open(src_png).save(str(dest_webp), 'WEBP', quality=90, lossless=False)
        except Exception:
            dest_png = dest_webp.with_suffix('.png')
            shutil.copy2(src_png, dest_png)
            dest_webp = dest_png

        data["image"] = f"/{dest_webp.relative_to(public_dir)}"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        exported += 1

    return exported


# ============================================================================
# 索引与聚合文件生成
# ============================================================================
INDEX_FIELDS = ["id", "name", "nameZh", "slot", "tier", "rarity", "material", "image", "tags"]


def _build_slot_index(category_dir: Path) -> Tuple[Dict[str, list], list]:
    """为 weapons/ 或 armor/ 目录构建按 slot 分类的索引"""
    slot_index = {}
    all_items = []
    if not category_dir.exists():
        return slot_index, all_items
    for slot_dir in category_dir.iterdir():
        if not slot_dir.is_dir():
            continue
        slot_name = slot_dir.name
        slot_index[slot_name] = []
        for json_file in sorted(slot_dir.glob("*.json")):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            item = {k: data.get(k) for k in INDEX_FIELDS if data.get(k) is not None}
            slot_index[slot_name].append(item)
            all_items.append(item)
    return slot_index, all_items


def generate_index_and_bundles(cfg: Config, weapon_count: int, armor_count: int):
    """生成 index.json、weapons.json、armor.json、all.json"""
    weapons_index, all_weapons = _build_slot_index(cfg.json_dir / "weapons")
    armor_index, all_armor = _build_slot_index(cfg.json_dir / "armor")

    index = {"version": cfg.version, "weapons": weapons_index, "armor": armor_index}
    with open(cfg.json_dir / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    log_success(f"索引文件: {cfg.json_dir / 'index.json'}")

    public_dir = cfg.json_dir.parent / "public"
    public_dir.mkdir(parents=True, exist_ok=True)

    for filename, items in [("weapons.json", all_weapons), ("armor.json", all_armor)]:
        bundle = {"version": cfg.version, "count": len(items), "items": items}
        with open(public_dir / filename, 'w', encoding='utf-8') as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)

    all_bundle = {
        "version": cfg.version,
        "weapons": {"count": len(all_weapons), "items": all_weapons},
        "armor": {"count": len(all_armor), "items": all_armor},
    }
    with open(public_dir / "all.json", 'w', encoding='utf-8') as f:
        json.dump(all_bundle, f, ensure_ascii=False, indent=2)

    log_success(f"聚合文件: weapons.json({len(all_weapons)}), armor.json({len(all_armor)}), all.json")


def generate_terminology(cfg: Config, terminology: Dict[str, Dict[str, str]]):
    """生成术语对照表 terminology.json"""
    used_keys = set()
    for mapping in ALL_PROP_MAPPINGS:
        used_keys.update(mapping.keys())
    for field, _ in DAMAGE_FIELDS:
        used_keys.add(field)
    for field, _ in BODY_PART_FIELDS:
        used_keys.add(field)

    terms = []
    for csv_key in sorted(used_keys):
        if csv_key not in terminology:
            continue
        t = terminology[csv_key]
        json_key = CSV_TO_JSON_KEY.get(csv_key, csv_key)
        entry = {
            "key": csv_key,
            "jsonKey": json_key,
            "nameEn": t.get('nameEn', ''),
            "nameZh": t.get('nameZh', ''),
        }
        if t.get('descEn'):
            entry["descEn"] = t['descEn']
        if t.get('descZh'):
            entry["descZh"] = t['descZh']
        terms.append(entry)

    public_dir = cfg.json_dir.parent / "public"
    with open(public_dir / "terminology.json", 'w', encoding='utf-8') as f:
        json.dump({"version": cfg.version, "count": len(terms), "terms": terms},
                  f, ensure_ascii=False, indent=2)
    log_success(f"术语对照表: terminology.json({len(terms)} 条)")


# ============================================================================
# Step 5: 转换为 JSON
# ============================================================================
def _write_item_json(cfg: Config, category: str, slot_folder: str, file_name: str, data: Dict):
    slot_dir = cfg.json_dir / category / slot_folder
    slot_dir.mkdir(parents=True, exist_ok=True)
    with open(slot_dir / f"{file_name}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _process_weapons(cfg: Config, name_map: Dict, desc_map: Dict, stats_map: Dict) -> Tuple[int, set]:
    weapons_csv = cfg.extracted_dir / "weapons.csv"
    if not weapons_csv.exists():
        return 0, set()

    count = 0
    slots = set()
    with open(weapons_csv, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            result = convert_weapon(row, name_map, desc_map, stats_map, cfg)
            if result:
                data, slot_folder, file_name = result
                _write_item_json(cfg, 'weapons', slot_folder, file_name, data)
                count += 1
                slots.add(slot_folder)
    return count, slots


def _process_armor(cfg: Config, name_map: Dict, desc_map: Dict, stats_map: Dict) -> Tuple[int, set]:
    armor_csv = cfg.extracted_dir / "armor.csv"
    if not armor_csv.exists():
        return 0, set()

    armor_rows = []
    with open(armor_csv, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            armor_rows.append(row)

    variant_of, base_of = build_variant_map(armor_rows)
    skip_names = set(variant_of.keys())

    name_to_row = {r.get('name', '').strip(): r for r in armor_rows}

    count = 0
    slots = set()
    for row in armor_rows:
        name = row.get('name', '').strip()
        if name in skip_names:
            continue

        result = convert_armor(row, name_map, desc_map, stats_map, cfg)
        if not result:
            continue
        data, slot_folder, file_name = result

        variant_name = base_of.get(name)
        if variant_name and variant_name in name_to_row:
            v_result = convert_armor(name_to_row[variant_name], name_map, desc_map, stats_map, cfg)
            if v_result:
                v_data = v_result[0]
                variant_props = {
                    "id": v_data["id"],
                    "name": v_data["name"],
                    "nameZh": v_data.get("nameZh", ""),
                    "durability": v_data.get("durability"),
                    "properties": v_data.get("properties", {}),
                }
                if v_data.get("tags"):
                    variant_props["tags"] = v_data["tags"]
                data["variant"] = variant_props

        _write_item_json(cfg, 'armor', slot_folder, file_name, data)
        count += 1
        slots.add(slot_folder)

    return count, slots


def step5_convert_to_json(cfg: Config) -> bool:
    log_step(5, 5, "转换为 JSON 格式（按 slot 分类）")

    if cfg.json_dir.exists():
        shutil.rmtree(cfg.json_dir)
    cfg.json_dir.mkdir(parents=True, exist_ok=True)

    log_info("加载中文名称和描述...")
    name_map, desc_map = parse_translations(cfg)
    log_success(f"找到 {len(name_map)} 个中文名称, {len(desc_map)} 个描述")

    log_info("加载 items_stats 数据...")
    stats_map = load_items_stats(cfg)
    log_success(f"找到 {len(stats_map)} 个物品统计")

    log_info("加载官方术语映射...")
    terminology = load_attributes_terminology(cfg)
    log_success(f"找到 {len(terminology)} 个官方术语")

    weapon_count, weapon_slots = _process_weapons(cfg, name_map, desc_map, stats_map)
    log_success(f"武器: {weapon_count} 个，分布在 {len(weapon_slots)} 个 slot 文件夹")

    armor_count, armor_slots = _process_armor(cfg, name_map, desc_map, stats_map)
    log_success(f"护甲: {armor_count} 个，分布在 {len(armor_slots)} 个 slot 文件夹")

    generate_index_and_bundles(cfg, weapon_count, armor_count)
    generate_terminology(cfg, terminology)

    if cfg.sprites_dump.exists():
        log_info("关联 sprite 图片到装备数据...")
        sprite_map = build_sprite_map(cfg.sprites_dump)
        log_info(f"找到 {len(sprite_map)} 个 sprite 映射")
        exported = export_sprite_images(cfg, sprite_map)
        log_success(f"已导出 {exported} 个装备图片 (webp)")

    return weapon_count > 0 or armor_count > 0


# ============================================================================
# Main Pipeline
# ============================================================================
STEP_NAMES = {
    '1': 0, 'unpack': 0,
    '2': 1, 'strings': 1,
    '3': 2, 'tables': 2,
    '4': 3, 'sprites': 3,
    '5': 4, 'json': 4,
}

STEPS = [
    ("解包 data.win", step1_unpack),
    ("提取字符串资源", step2_extract_strings),
    ("提取 Table 数据", step3_extract_tables),
    ("提取 Sprite 图片", step4_extract_sprites),
    ("转换为 JSON", step5_convert_to_json),
]


def parse_step_spec(spec: str) -> List[int]:
    selected = set()
    for part in spec.split(','):
        part = part.strip().lower()
        if '-' in part and len(part.split('-')) == 2:
            a, b = part.split('-')
            a_idx = STEP_NAMES.get(a)
            b_idx = STEP_NAMES.get(b)
            if a_idx is not None and b_idx is not None:
                selected.update(range(a_idx, b_idx + 1))
            else:
                lo, hi = int(a), int(b)
                selected.update(range(lo - 1, min(hi, len(STEPS))))
        elif part in STEP_NAMES:
            selected.add(STEP_NAMES[part])
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < len(STEPS):
                    selected.add(idx)
            except ValueError:
                pass
    return sorted(selected)


def main():
    cfg = parse_args()

    print("=" * 80)
    print("紫色晶石装备数据提取 Pipeline")
    print("=" * 80)

    if cfg.step_spec:
        selected = parse_step_spec(cfg.step_spec)
        log_info(f"只运行步骤: {', '.join(str(i + 1) for i in selected)}")
    else:
        selected = list(range(len(STEPS)))

    success = True
    for i in selected:
        name, step_func = STEPS[i]
        try:
            if not step_func(cfg):
                success = False
                log_error(f"步骤 {i + 1} 失败")
                break
        except Exception as e:
            success = False
            log_error(f"步骤 {i + 1} 出错: {e}")
            import traceback
            traceback.print_exc()
            break

    print("\n" + "=" * 80)
    if success:
        print(f"{Colors.GREEN}✓ Pipeline 执行成功!{Colors.END}")
        print(f"输出目录: {cfg.json_dir}")

        weapons_dir = cfg.json_dir / "weapons"
        armor_dir = cfg.json_dir / "armor"
        weapon_slots = [d for d in weapons_dir.iterdir() if d.is_dir()] if weapons_dir.exists() else []
        armor_slots = [d for d in armor_dir.iterdir() if d.is_dir()] if armor_dir.exists() else []
        weapon_count = sum(len(list(d.glob("*.json"))) for d in weapon_slots)
        armor_count = sum(len(list(d.glob("*.json"))) for d in armor_slots)

        print(f"\n武器: {weapon_count} 个")
        print(f"  Slot 分类: {', '.join(sorted(d.name for d in weapon_slots))}")
        print(f"\n护甲: {armor_count} 个")
        print(f"  Slot 分类: {', '.join(sorted(d.name for d in armor_slots))}")
        print(f"\n总计: {weapon_count + armor_count} 个")
    else:
        print(f"{Colors.RED}✗ Pipeline 执行失败{Colors.END}")
    print("=" * 80)


if __name__ == "__main__":
    main()
