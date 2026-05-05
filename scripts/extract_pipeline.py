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
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"


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
    match = re.search(r"return\s*\[([\s\S]*?)\];\s*}", content)
    if not match:
        return None

    array_content = match.group(1)
    items = []
    i = 0
    while i < len(array_content):
        while i < len(array_content) and array_content[i] in " \t\n\r,":
            i += 1
        if i >= len(array_content):
            break
        if array_content[i] == '"':
            j = i + 1
            while j < len(array_content):
                if array_content[j] == "\\" and j + 1 < len(array_content):
                    j += 2
                elif array_content[j] == '"':
                    break
                else:
                    j += 1
            items.append(array_content[i + 1 : j])
            i = j + 1
        else:
            i += 1
    return items if items else None


def parse_gml_table(file_path: Path) -> Optional[Dict[str, Any]]:
    """解析 GML 文件中的 table 数据，返回 {headers, rows, count}"""
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    items = parse_gml_string_array(content)
    if not items:
        return None

    headers = items[0].split(";")
    rows = []
    for line in items[1:]:
        if line.startswith("//") or line.startswith("[") or not line.strip():
            continue
        row = line.split(";")
        if row and any(cell.strip() for cell in row):
            rows.append(row)

    return {"headers": headers, "rows": rows, "count": len(rows)}


# ============================================================================
# 版本提取与参数解析
# ============================================================================
def extract_version_from_game(game_data: Path, utmt_cli: Path) -> Optional[str]:
    temp_dir = Path("/tmp/version_extract")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    try:
        subprocess.run(
            [
                str(utmt_cli),
                "dump",
                str(game_data),
                "-c",
                "gml_GlobalScript_scr_debug_get_source_hash",
                "-o",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        version_file = (
            temp_dir / "CodeEntries" / "gml_GlobalScript_scr_debug_get_source_hash.gml"
        )
        if version_file.exists():
            content = version_file.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'_message\s*=\s*"([^"]+)"', content)
            if match:
                version = re.sub(r"-vm$", "", match.group(1))
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
        """,
    )

    parser.add_argument("game_data", type=Path, help="游戏数据文件路径 (data.win)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("json_output"),
        help="JSON 输出目录 (默认: json_output)",
    )
    parser.add_argument(
        "-u",
        "--utmt",
        type=Path,
        default=Path.home() / "UTMT" / "UndertaleModCli",
        help="UndertaleModCli 工具路径",
    )
    parser.add_argument("--unpacked", type=Path, default=None, help="解包文件存放目录")
    parser.add_argument("--tables", type=Path, default=None, help="CSV 表格存放目录")
    parser.add_argument(
        "--strings",
        type=Path,
        default=Path("/tmp/strings_dump/strings.txt"),
        help="字符串转储文件路径",
    )
    parser.add_argument(
        "--version", type=str, default=None, help="游戏版本号 (默认: 自动提取)"
    )
    parser.add_argument(
        "-s",
        "--step",
        type=str,
        default=None,
        help="只运行指定阶段 (1-6 或名称: unpack,strings,tables,sprites,json,mobs)",
    )

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
    "gml_GlobalScript_table_items_stats",
    "gml_GlobalScript_table_attributes",
    "gml_GlobalScript_table_mobs",
    "gml_GlobalScript_table_mobs_stats",
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
        key_files = [
            "table_weapons",
            "table_armor",
            "table_items_stats",
            "table_attributes",
            "table_mobs",
            "table_mobs_stats",
        ]
        if all(any(cfg.unpacked_dir.glob(f"*{f}*.gml")) for f in key_files):
            log_info("检测到已有完整解包数据，跳过解包步骤")
            gml_files = list(cfg.unpacked_dir.glob("*.gml"))
            log_success(f"使用现有 {len(gml_files)} 个 GML 文件")
            return True

    if cfg.unpacked_dir.exists():
        shutil.rmtree(cfg.unpacked_dir)
    cfg.unpacked_dir.mkdir(parents=True, exist_ok=True)

    tables_to_extract = TABLES_TO_EXTRACT
    log_info(f"提取 {len(tables_to_extract)} 个 table 脚本...")

    extracted_count = 0
    temp_dir = Path("/tmp/t")
    total = len(tables_to_extract)

    for i, table in enumerate(tables_to_extract, 1):
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            subprocess.run(
                [
                    str(cfg.utmt_cli),
                    "dump",
                    str(cfg.game_data),
                    "-c",
                    table,
                    "-o",
                    "/tmp/t",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            code_entries = temp_dir / "CodeEntries"
            if code_entries.exists():
                for gml_file in code_entries.glob("*.gml"):
                    shutil.copy2(gml_file, cfg.unpacked_dir / gml_file.name)
                    extracted_count += 1
            log_info(f"进度: {i}/{total} - 已提取 {extracted_count} 个文件")
        except Exception as e:
            log_error(f"提取 {table} 出错: {e}")

    if extracted_count > 0:
        log_success(f"提取了 {extracted_count} 个 table GML 文件")
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
            [
                str(cfg.utmt_cli),
                "dump",
                str(cfg.game_data),
                "-s",
                "-o",
                str(strings_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
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
def discover_table_files(unpacked_dir: Path) -> List[Tuple[str, str]]:
    """自动发现所有 gml_GlobalScript_table_*.gml 文件
    返回 [(name, filename), ...] 列表
    """
    tables = []
    prefix = "gml_GlobalScript_table_"
    suffix = ".gml"

    if not unpacked_dir.exists():
        return tables

    for f in unpacked_dir.iterdir():
        if f.name.startswith(prefix) and f.name.endswith(suffix):
            name = f.name[len(prefix) : -len(suffix)]
            tables.append((name, f.name))

    return sorted(tables, key=lambda x: x[0])


def step3_extract_tables(cfg: Config) -> bool:
    log_step(3, 5, "提取 Table 数据为 CSV")

    if cfg.extracted_dir.exists():
        shutil.rmtree(cfg.extracted_dir)
    cfg.extracted_dir.mkdir(parents=True, exist_ok=True)

    table_files = discover_table_files(cfg.unpacked_dir)
    log_info(f"发现 {len(table_files)} 个 table 文件")

    extracted = 0
    for name, filename in table_files:
        file_path = cfg.unpacked_dir / filename
        if not file_path.exists():
            continue
        data = parse_gml_table(file_path)
        if data and data["rows"]:
            with open(
                cfg.extracted_dir / f"{name}.csv", "w", newline="", encoding="utf-8-sig"
            ) as f:
                csv.writer(f).writerows([data["headers"]] + data["rows"])
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
    csx_content = """using System.Text;
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
""".replace("SPRITES_OUTPUT_DIR", str(sprites_dir.resolve()))
    csx_script.write_text(csx_content, encoding="utf-8")

    log_info("提取 sprite 图片（可能需要几分钟）...")

    try:
        subprocess.run(
            [str(cfg.utmt_cli), "load", str(cfg.game_data), "-s", str(csx_script)],
            capture_output=True,
            text=True,
            timeout=300,
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
    if not value or value.strip() == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value: str, default: float = 0.0) -> float:
    if not value or value.strip() == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def to_kebab_case(name: str) -> str:
    name = re.sub(r"[^\w\s]", " ", name)
    words = name.split()
    return "-".join(word.lower() for word in words if word)


def _extract_short_name(text: str) -> str:
    if not text:
        return ""
    if len(text) <= 40 and "##" not in text:
        return text
    for sep in ["##", ".#", "."]:
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
    with open(stats_file, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            item_id = row.get("id", "").strip()
            if item_id:
                stats_map[item_id.lower()] = row
    return stats_map


def parse_translations(
    cfg: Config,
) -> Tuple[Dict[str, str], Dict[str, Tuple[str, str]]]:
    """解析名称翻译和描述。策略：同一 key 多行时，en 最短为名称，最长为描述"""
    name_map = {}
    desc_map = {}

    if not cfg.strings_dump.exists():
        return name_map, desc_map

    content = cfg.strings_dump.read_text(encoding="utf-8", errors="ignore")
    key_lines = defaultdict(list)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if len(parts) < 4:
            continue
        item_name = parts[0].strip()
        english = parts[2].strip() if len(parts) > 2 else ""
        chinese = parts[3].strip() if len(parts) > 3 else ""
        if not item_name or item_name.startswith("//"):
            continue
        if not english or not any("\u4e00" <= c <= "\u9fff" for c in chinese):
            continue
        key_lines[item_name.lower()].append((english, chinese))

    for key, lines in key_lines.items():
        if len(lines) == 1:
            en, zh = lines[0]
            if len(en) <= 50 and len(zh) <= 50 and "." not in en:
                name_map[key] = zh
            else:
                desc_map[key] = (en, zh)
        else:
            sorted_lines = sorted(lines, key=lambda x: len(x[0]))
            name_en, name_zh = sorted_lines[0]
            desc_en, desc_zh = sorted_lines[-1]
            if len(name_en) <= 50 and len(name_zh) <= 50:
                name_map[key] = name_zh
            if len(desc_en) > 30 or "." in desc_en:
                desc_map[key] = (desc_en, desc_zh)

    return name_map, desc_map


def load_attributes_terminology(cfg: Config) -> Dict[str, Dict[str, str]]:
    """从 table_attributes.gml 加载官方术语映射，只取 // TRADE STATS 之前的战斗属性"""
    gml_file = cfg.unpacked_dir / "gml_GlobalScript_table_attributes.gml"
    if not gml_file.exists():
        return {}

    content = gml_file.read_text(encoding="utf-8", errors="ignore")
    items = parse_gml_string_array(content)
    if not items:
        return {}

    terminology = {}
    for item in items[2:]:
        parts = item.split(";")
        if len(parts) < 4:
            continue
        key = parts[0].strip()
        en = parts[2].strip()
        zh = parts[3].strip()
        if en.startswith("// TRADE STATS") or zh.startswith("// TRADE STATS"):
            break
        if key and not key.startswith("//") and (en or zh):
            en_short = _extract_short_name(en)
            zh_short = _extract_short_name(zh)
            entry = {"nameEn": en_short, "nameZh": zh_short}
            if en != en_short:
                entry["descEn"] = en
            if zh != zh_short:
                entry["descZh"] = zh
            terminology[key] = entry

    return terminology


# ============================================================================
# 属性映射与提取
# ============================================================================
COMBAT_PROPS = {
    "Hit_Chance": "accuracy",
    "CRT": "critChance",
    "CRTD": "critEfficiency",
    "CTA": "counterChance",
    "FMB": "fumbleChance",
    "Armor_Piercing": "armorPenetration",
    "Armor_Damage": "armorDamage",
    "Bodypart_Damage": "bodypartDamage",
    "PRR": "blockChance",
    "Block_Power": "blockPower",
    "Block_Recovery": "blockRecovery",
    "Bleeding_Chance": "bleedingChance",
    "Daze_Chance": "dazeChance",
    "Stun_Chance": "stunChance",
    "Knockback_Chance": "knockbackChance",
    "Immob_Chance": "immobilizationChance",
    "Stagger_Chance": "staggerChance",
    "MP": "maxMana",
    "MP_Restoration": "manaRestoration",
    "max_hp": "maxHealth",
    "Health_Restoration": "healthRestoration",
    "Healing_Received": "healingReceived",
    "Lifesteal": "lifesteal",
    "Manasteal": "manasteal",
    "Abilities_Energy_Cost": "abilitiesEnergyCost",
    "Skills_Energy_Cost": "skillsEnergyCost",
    "Spells_Energy_Cost": "spellsEnergyCost",
    "Cooldown_Reduction": "cooldownReduction",
    "Magic_Power": "magicPower",
    "Miscast_Chance": "miscastChance",
    "Miracle_Chance": "miracleChance",
    "Miracle_Power": "miraclePower",
    "Bonus_Range": "bonusRange",
    "Damage_Received": "damageReceived",
    "Fatigue_Gain": "fatigueGain",
}

ARMOR_ONLY_PROPS = {
    "DEF": "defense",
    "EVS": "evasion",
    "Crit_Avoid": "critAvoid",
    "Fortitude": "fortitude",
    "VSN": "vision",
    "Weapon_Damage": "weaponDamage",
    "Damage_Returned": "damageReturned",
}

RESISTANCE_MAP = {
    "Bleeding_Resistance": "bleeding",
    "Knockback_Resistance": "knockback",
    "Stun_Resistance": "stun",
    "Pain_Resistance": "pain",
    "Physical_Resistance": "physical",
    "Nature_Resistance": "nature",
    "Magic_Resistance": "magic",
    "Slashing_Resistance": "slashing",
    "Piercing_Resistance": "piercing",
    "Blunt_Resistance": "blunt",
    "Rending_Resistance": "rending",
    "Fire_Resistance": "fire",
    "Shock_Resistance": "shock",
    "Poison_Resistance": "poison",
    "Caustic_Resistance": "caustic",
    "Frost_Resistance": "frost",
    "Arcane_Resistance": "arcane",
    "Unholy_Resistance": "unholy",
    "Sacred_Resistance": "sacred",
    "Psionic_Resistance": "psionic",
}

MAGIC_POWER_MAP = {
    "Pyromantic_Power": "pyromantic",
    "Geomantic_Power": "geomantic",
    "Venomantic_Power": "venomantic",
    "Electromantic_Power": "electromantic",
    "Cryomantic_Power": "cryomantic",
    "Arcanistic_Power": "arcanistic",
    "Astromantic_Power": "astromantic",
    "Psimantic_Power": "psimantic",
}

DAMAGE_FIELDS = [
    ("Slashing_Damage", "slashing"),
    ("Piercing_Damage", "piercing"),
    ("Blunt_Damage", "blunt"),
    ("Rending_Damage", "rending"),
    ("Fire_Damage", "fire"),
    ("Shock_Damage", "shock"),
    ("Poison_Damage", "poison"),
    ("Caustic_Damage", "caustic"),
    ("Frost_Damage", "frost"),
    ("Arcane_Damage", "arcane"),
    ("Unholy_Damage", "unholy"),
    ("Sacred_Damage", "sacred"),
    ("Psionic_Damage", "psionic"),
]

BODY_PART_FIELDS = [
    ("Head_DEF", "head"),
    ("Body_DEF", "body"),
    ("Arms_DEF", "arms"),
    ("Legs_DEF", "legs"),
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
    return {
        json_field: val
        for csv_field, json_field in mapping.items()
        if (val := safe_int(row.get(csv_field, ""), 0)) != 0
    }


def extract_damages(row: Dict[str, str]) -> Tuple[Dict[str, int], str, int]:
    damages = {}
    primary_type = "slashing"
    primary_value = 0
    for field, dtype in DAMAGE_FIELDS:
        val = safe_int(row.get(field, ""), 0)
        if val > 0:
            damages[dtype] = val
            if val > primary_value:
                primary_type = dtype
                primary_value = val
    return damages, primary_type, primary_value


def extract_body_parts(row: Dict[str, str]) -> Dict[str, int]:
    return {
        pname: val
        for field, pname in BODY_PART_FIELDS
        if (val := safe_int(row.get(field, ""), 0)) > 0
    }


# ============================================================================
# 装备转换
# ============================================================================
SLOT_FOLDER_MAP = {
    "sword": "swords",
    "axe": "axes",
    "mace": "maces",
    "dagger": "daggers",
    "2hsword": "two-handed-swords",
    "2haxe": "two-handed-axes",
    "2hmace": "two-handed-maces",
    "2hStaff": "staves",
    "spear": "spears",
    "bow": "bows",
    "crossbow": "crossbows",
    "sling": "slings",
    "shield": "shields",
    "Head": "helmets",
    "Chest": "chests",
    "Arms": "gloves",
    "Legs": "boots",
    "Waist": "belts",
    "Ring": "rings",
    "Amulet": "amulets",
    "Back": "cloaks",
}

VALID_TAGS = {
    "aldor",
    "elven",
    "fjall",
    "nistra",
    "special",
    "unique",
    "dungeon",
    "exc",
    "magic",
    "undead",
}


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


def find_translations(
    name: str, name_map: Dict[str, str], desc_map: Dict[str, Tuple[str, str]]
) -> Tuple[str, str, str]:
    """查找名称和描述的翻译，返回 (zh_name, en_desc, zh_desc)"""
    key = name.lower()
    zh_name = name_map.get(key, "")
    en_desc, zh_desc = desc_map.get(key, ("", ""))

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
            zh_name = name_map.get(alt_key, "")
        if not en_desc:
            en_desc, zh_desc = desc_map.get(alt_key, ("", ""))
        if zh_name and en_desc:
            break

    return zh_name, en_desc, zh_desc


def _build_base_data(
    row: Dict[str, str],
    category: str,
    name_map: Dict[str, str],
    desc_map: Dict[str, Tuple[str, str]],
    properties: Dict,
) -> Tuple[Dict, str, str]:
    """构建武器/护甲共用的基础数据字典，返回 (data, slot_folder, file_name)"""
    name = row.get("name", "").strip()
    file_name = to_kebab_case(name)
    slot = row.get("Slot", "").strip()
    slot_folder = get_slot_folder(slot)
    zh_name, en_desc, zh_desc = find_translations(name, name_map, desc_map)
    tags = parse_tags(row.get("tags", ""))

    data = {
        "id": file_name,
        "name": name,
        "nameZh": zh_name,
        "slot": slot.lower(),
        "tier": safe_int(row.get("Tier", ""), 1),
        "rarity": row.get("rarity", "Common").lower(),
        "material": row.get("Mat", "metal").lower(),
        "image": f"/images/{category}/{slot_folder}/{file_name}.webp",
        "durability": safe_int(row.get("MaxDuration", ""), 100),
        "price": safe_int(row.get("Price", ""), 0),
        "properties": properties,
    }

    if tags:
        data["tags"] = tags
    if en_desc:
        data["description"] = en_desc
    if zh_desc:
        data["descriptionZh"] = zh_desc

    return data, slot_folder, file_name


def convert_weapon(
    row: Dict[str, str],
    name_map: Dict[str, str],
    desc_map: Dict[str, Tuple[str, str]],
    stats_map: Dict[str, Dict[str, str]],
    cfg: Config,
) -> Optional[Tuple[Dict, str, str]]:
    name = row.get("name", "").strip()
    if not name:
        return None

    item_id = row.get("id", "").strip()
    properties = extract_props(row, COMBAT_PROPS)

    if item_id and item_id.lower() in stats_map:
        stats_row = stats_map[item_id.lower()]
        resistances = extract_props(stats_row, RESISTANCE_MAP)
        if resistances:
            properties["resistances"] = resistances
        properties.update(
            extract_props(
                stats_row,
                {
                    "Received_XP": "experienceGain",
                    "VSN": "vision",
                    "Fortitude": "fortitude",
                },
            )
        )

    damages, primary_type, primary_value = extract_damages(row)
    if len(damages) > 1:
        properties["damages"] = damages
    magic_powers = extract_props(row, MAGIC_POWER_MAP)
    if magic_powers:
        properties["magicPowers"] = magic_powers

    data, slot_folder, file_name = _build_base_data(
        row, "weapons", name_map, desc_map, properties
    )

    data["damage"] = {"value": primary_value, "type": primary_type}
    range_val = safe_int(row.get("Rng", ""), 0)
    if range_val > 0:
        data["range"] = range_val

    return data, slot_folder, file_name


def convert_armor(
    row: Dict[str, str],
    name_map: Dict[str, str],
    desc_map: Dict[str, Tuple[str, str]],
    stats_map: Dict[str, Dict[str, str]],
    cfg: Config,
) -> Optional[Tuple[Dict, str, str]]:
    name = row.get("name", "").strip()
    if not name:
        return None

    item_id = row.get("id", "").strip()
    armor_class = row.get("class", "").strip()

    all_prop_mapping = {**COMBAT_PROPS, **ARMOR_ONLY_PROPS}
    properties = extract_props(row, all_prop_mapping)

    resistances = extract_props(row, RESISTANCE_MAP)
    if item_id and item_id.lower() in stats_map:
        stats_row = stats_map[item_id.lower()]
        for json_field, val in extract_props(stats_row, RESISTANCE_MAP).items():
            if json_field not in resistances:
                resistances[json_field] = val
        for k, v in extract_props(
            stats_row,
            {
                "Received_XP": "experienceGain",
                "Fatigue_Gain": "fatigueGain",
            },
        ).items():
            if k not in properties:
                properties[k] = v

    if resistances:
        properties["resistances"] = resistances
    magic_powers = extract_props(row, MAGIC_POWER_MAP)
    if magic_powers:
        properties["magicPowers"] = magic_powers
    body_parts = extract_body_parts(row)
    if body_parts:
        properties["bodyPartProtection"] = body_parts

    data, slot_folder, file_name = _build_base_data(
        row, "armor", name_map, desc_map, properties
    )

    data["class"] = armor_class.lower() if armor_class else ""
    if row.get("fireproof", "").strip() == "1":
        data["fireproof"] = True

    return data, slot_folder, file_name


# ============================================================================
# 变种检测
# ============================================================================
def build_variant_map(
    armor_rows: List[Dict[str, str]],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """构建变种映射，返回 (variant_of, base_of)

    variant_of: {变种名 → 基础名}
    base_of:    {基础名 → 变种名}
    仅处理 class=heavy 且有 visorSwitch 的重甲头盔
    """
    variant_of = {}
    for row in armor_rows:
        visor = row.get("visorSwitch", "").strip()
        name = row.get("name", "").strip()
        armor_class = row.get("class", "").strip().lower()
        if not visor or armor_class != "heavy":
            continue
        if name.startswith("Open "):
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
        sprite_name = re.sub(r"_0$", "", re.sub(r"^s_inv_", "", png_file.stem))
        sprite_map[sprite_name.lower()] = png_file
    return sprite_map


def name_to_sprite_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def find_sprite(name: str, sprite_map: Dict[str, Path]) -> Optional[Path]:
    key = name_to_sprite_key(name)
    if key in sprite_map:
        return sprite_map[key]
    if name.startswith("Open "):
        key_no_open = name_to_sprite_key(name[5:])
        if key_no_open in sprite_map:
            return sprite_map[key_no_open]
    return None


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
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", "")
        item_id = data.get("id", "")
        if not name or not item_id:
            continue

        src_png = find_sprite(name, sprite_map)
        if not src_png:
            continue
        rel = json_file.relative_to(cfg.json_dir)
        parts = list(rel.parts)
        parts[-1] = f"{item_id}.webp"
        dest_webp = images_dir / Path(*parts)
        dest_webp.parent.mkdir(parents=True, exist_ok=True)

        try:
            Image.open(src_png).save(str(dest_webp), "WEBP", quality=90, lossless=False)
        except Exception:
            dest_png = dest_webp.with_suffix(".png")
            shutil.copy2(src_png, dest_png)
            dest_webp = dest_png

        data["image"] = f"/{dest_webp.relative_to(public_dir)}"

        v = data.get("variant")
        if v:
            v_id = v.get("id", "")
            if v_id:
                src_png_v = src_png.with_name(src_png.name.replace("_0.", "_2."))
                if src_png_v.exists():
                    parts_v = list(parts)
                    parts_v[-1] = f"{v_id}.webp"
                    dest_webp_v = images_dir / Path(*parts_v)
                    dest_webp_v.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        Image.open(src_png_v).save(
                            str(dest_webp_v), "WEBP", quality=90, lossless=False
                        )
                        v["image"] = f"/{dest_webp_v.relative_to(public_dir)}"
                    except Exception:
                        pass

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        exported += 1

    return exported


# ============================================================================
# 索引与聚合文件生成
# ============================================================================
INDEX_FIELDS = [
    "id",
    "name",
    "nameZh",
    "slot",
    "tier",
    "rarity",
    "material",
    "image",
    "tags",
]


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
            with open(json_file, "r", encoding="utf-8") as f:
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
    with open(cfg.json_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    log_success(f"索引文件: {cfg.json_dir / 'index.json'}")

    public_dir = cfg.json_dir.parent / "public"
    public_dir.mkdir(parents=True, exist_ok=True)

    for filename, items in [("weapons.json", all_weapons), ("armor.json", all_armor)]:
        bundle = {"version": cfg.version, "count": len(items), "items": items}
        with open(public_dir / filename, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)

    all_bundle = {
        "version": cfg.version,
        "weapons": {"count": len(all_weapons), "items": all_weapons},
        "armor": {"count": len(all_armor), "items": all_armor},
    }
    with open(public_dir / "all.json", "w", encoding="utf-8") as f:
        json.dump(all_bundle, f, ensure_ascii=False, indent=2)

    log_success(
        f"聚合文件: weapons.json({len(all_weapons)}), armor.json({len(all_armor)}), all.json"
    )


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
            "nameEn": t.get("nameEn", ""),
            "nameZh": t.get("nameZh", ""),
        }
        if t.get("descEn"):
            entry["descEn"] = t["descEn"]
        if t.get("descZh"):
            entry["descZh"] = t["descZh"]
        terms.append(entry)

    public_dir = cfg.json_dir.parent / "public"
    with open(public_dir / "terminology.json", "w", encoding="utf-8") as f:
        json.dump(
            {"version": cfg.version, "count": len(terms), "terms": terms},
            f,
            ensure_ascii=False,
            indent=2,
        )
    log_success(f"术语对照表: terminology.json({len(terms)} 条)")


# ============================================================================
# Step 5: 转换为 JSON
# ============================================================================
def _write_item_json(
    cfg: Config, category: str, slot_folder: str, file_name: str, data: Dict
):
    slot_dir = cfg.json_dir / category / slot_folder
    slot_dir.mkdir(parents=True, exist_ok=True)
    with open(slot_dir / f"{file_name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _process_weapons(
    cfg: Config, name_map: Dict, desc_map: Dict, stats_map: Dict
) -> Tuple[int, set]:
    weapons_csv = cfg.extracted_dir / "weapons.csv"
    if not weapons_csv.exists():
        return 0, set()

    count = 0
    slots = set()
    with open(weapons_csv, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            result = convert_weapon(row, name_map, desc_map, stats_map, cfg)
            if result:
                data, slot_folder, file_name = result
                _write_item_json(cfg, "weapons", slot_folder, file_name, data)
                count += 1
                slots.add(slot_folder)
    return count, slots


def _process_armor(
    cfg: Config, name_map: Dict, desc_map: Dict, stats_map: Dict
) -> Tuple[int, set]:
    armor_csv = cfg.extracted_dir / "armor.csv"
    if not armor_csv.exists():
        return 0, set()

    armor_rows = []
    with open(armor_csv, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            armor_rows.append(row)

    variant_of, base_of = build_variant_map(armor_rows)
    skip_names = set(variant_of.keys())

    name_to_row = {r.get("name", "").strip(): r for r in armor_rows}

    count = 0
    slots = set()
    for row in armor_rows:
        name = row.get("name", "").strip()
        if name in skip_names:
            continue

        result = convert_armor(row, name_map, desc_map, stats_map, cfg)
        if not result:
            continue
        data, slot_folder, file_name = result

        variant_name = base_of.get(name)
        if variant_name and variant_name in name_to_row:
            v_result = convert_armor(
                name_to_row[variant_name], name_map, desc_map, stats_map, cfg
            )
            if v_result:
                v_data = v_result[0]
                variant_props = {
                    "id": v_data["id"],
                    "name": v_data["name"],
                    "nameZh": v_data.get("nameZh", ""),
                    "image": v_data.get("image", ""),
                    "durability": v_data.get("durability"),
                    "properties": v_data.get("properties", {}),
                }
                if v_data.get("tags"):
                    variant_props["tags"] = v_data["tags"]
                data["variant"] = variant_props

        _write_item_json(cfg, "armor", slot_folder, file_name, data)
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
# Step 6: 转换为怪物 JSON
# ============================================================================
def parse_mobs_translations(
    cfg: Config,
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """解析怪物名称和描述翻译，返回 (names, descriptions)
    names: {mob_id: {en, zh}}
    descriptions: {mob_id: {en, zh}}
    """
    mobs_file = cfg.extracted_dir / "mobs.csv"
    if not mobs_file.exists():
        return {}, {}

    names = {}
    descriptions = {}

    with open(mobs_file, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)

        en_idx = headers.index("English") if "English" in headers else 2
        zh_idx = headers.index("中文") if "中文" in headers else 3

        for row in reader:
            if not row or len(row) < 2:
                continue
            mob_id = row[0].strip()
            if not mob_id or mob_id.startswith("//") or mob_id.startswith("["):
                continue

            en_text = row[en_idx].strip() if en_idx < len(row) else ""
            zh_text = row[zh_idx].strip() if zh_idx < len(row) else ""

            # 第一行是名称，第二行是描述
            if mob_id not in names:
                names[mob_id] = {"en": en_text, "zh": zh_text}
            else:
                descriptions[mob_id] = {"en": en_text, "zh": zh_text}

    return names, descriptions


def categorize_mob_stats(row: Dict[str, str]) -> Dict[str, Any]:
    """将敌人属性分组并转换为驼峰命名"""

    attributes = {}
    combat = {}
    defense = {}
    offense = {}
    resistances = {}
    other = {}

    attr_mapping = {
        "HP": ("health", attributes),
        "MP": ("mana", attributes),
        "XP": ("experience", attributes),
        "VIS": ("vision", attributes),
        "Morale": ("morale", attributes),
        "IP": ("ip", attributes),
    }

    combat_mapping = {
        "Hit_Chance": ("hitChance", combat),
        "EVS": ("evasion", combat),
        "PRR": ("blockChance", combat),
        "Block_Power": ("blockPower", combat),
        "Block_Recovery": ("blockRecovery", combat),
        "Crit_Avoid": ("critAvoid", combat),
        "CRT": ("critChance", combat),
        "CRTD": ("critEfficiency", combat),
        "CTA": ("counterChance", combat),
        "FMB": ("fumble", combat),
        "Magic_Power": ("magicPower", combat),
        "Miscast_Chance": ("miscastChance", combat),
        "Miracle_Chance": ("miracleChance", combat),
        "Miracle_Power": ("miraclePower", combat),
        "MP_Restoration": ("manaRestoration", combat),
        "Cooldown_Reduction": ("cooldownReduction", combat),
        "Fortitude": ("fortitude", combat),
        "Health_Restoration": ("healthRestoration", combat),
        "Healing_Received": ("healingReceived", combat),
        "Lifesteal": ("lifesteal", combat),
        "Manasteal": ("manasteal", combat),
        "Bonus_Range": ("bonusRange", combat),
        "Damage_Received": ("damageReceived", combat),
        "Avoiding_Chance": ("avoidingChance", combat),
        "Damage_Returned": ("damageReturned", combat),
    }

    defense_mapping = {
        "Head_DEF": ("head", defense),
        "Body_DEF": ("body", defense),
        "Arms_DEF": ("arms", defense),
        "Legs_DEF": ("legs", defense),
        "Bleeding_Resistance": ("bleeding", resistances),
        "Knockback_Resistance": ("knockback", resistances),
        "Stun_Resistance": ("stun", resistances),
        "Pain_Resistance": ("pain", resistances),
        "Physical_Resistance": ("physical", resistances),
        "Natural_Resistance": ("natural", resistances),
        "Magical_Resistance": ("magical", resistances),
        "Slashing_Resistance": ("slashing", resistances),
        "Piercing_Resistance": ("piercing", resistances),
        "Blunt_Resistance": ("blunt", resistances),
        "Rending_Resistance": ("rending", resistances),
        "Fire_Resistance": ("fire", resistances),
        "Shock_Resistance": ("shock", resistances),
        "Poison_Resistance": ("poison", resistances),
        "Frost_Resistance": ("frost", resistances),
        "Caustic_Resistance": ("caustic", resistances),
        "Arcane_Resistance": ("arcane", resistances),
        "Unholy_Resistance": ("unholy", resistances),
        "Sacred_Resistance": ("sacred", resistances),
        "Psionic_Resistance": ("psionic", resistances),
    }

    offense_mapping = {
        "Bodypart_Damage": ("bodypartDamage", offense),
        "Armor_Piercing": ("armorPiercing", offense),
        "Total Damage": ("totalDamage", offense),
        "Slashing_Damage": ("slashing", offense),
        "Piercing_Damage": ("piercing", offense),
        "Blunt_Damage": ("blunt", offense),
        "Rending_Damage": ("rending", offense),
        "Fire_Damage": ("fire", offense),
        "Shock_Damage": ("shock", offense),
        "Poison_Damage": ("poison", offense),
        "Caustic_Damage": ("caustic", offense),
        "Frost_Damage": ("frost", offense),
        "Arcane_Damage": ("arcane", offense),
        "Unholy_Damage": ("unholy", offense),
        "Sacred_Damage": ("sacred", offense),
        "Psionic_Damage": ("psionic", offense),
        "Bleeding_Chance": ("bleedingChance", offense),
        "Daze_Chance": ("dazeChance", offense),
        "Stun_Chance": ("stunChance", offense),
        "Knockback_Chance": ("knockbackChance", offense),
        "Immob_Chance": ("immobilizationChance", offense),
        "Stagger_Chance": ("staggerChance", offense),
    }

    power_mapping = {
        "Pyromantic_Power": ("pyromantic", other),
        "Geomantic_Power": ("geomantic", other),
        "Venomantic_Power": ("venomantic", other),
        "Electromantic_Power": ("electromantic", other),
        "Cryomantic_Power": ("cryomantic", other),
        "Arcanistic_Power": ("arcanistic", other),
        "Astromantic_Power": ("astromantic", other),
        "Psimantic_Power": ("psimantic", other),
    }

    stat_mapping = {
        "STR k": ("strK", other),
        "AGL k": ("aglK", other),
        "Vitality k": ("vitalityK", other),
        "PRC k": ("prcK", other),
        "WIL k": ("wilK", other),
        "STR": ("str", attributes),
        "AGL": ("agl", attributes),
        "Vitality": ("vitality", attributes),
        "PRC": ("prc", attributes),
        "WIL": ("wil", attributes),
    }

    body_parts = {
        "Head": ("head", other),
        "Torso": ("torso", other),
        "Left_Leg": ("leftLeg", other),
        "Right_Leg": ("rightLeg", other),
        "Left_Hand": ("leftHand", other),
        "Right_Hand": ("rightHand", other),
    }

    flags = {
        "canBlock": ("canBlock", other),
        "Trap_Awareness": ("trapAwareness", other),
        "Trap_Disarm_Chance": ("trapDisarmChance", other),
        "canDisarm": ("canDisarm", other),
        "noTP": ("noTp", other),
        "night_vision": ("nightVision", other),
        "is_pyrophopic": ("isPyrophopic", other),
        "has_torch": ("hasTorch", other),
        "canSwim": ("canSwim", other),
        "Swimming_Cost": ("swimmingCost", other),
        "is_hostile": ("isHostile", other),
        "Bleeding_Immunity": ("bleedingImmunity", other),
        "Move_Immunity": ("moveImmunity", other),
        "Control_Immunity": ("controlImmunity", other),
        "Effect_Immunity": ("effectImmunity", other),
    }

    for key, value in row.items():
        if not value or not value.strip():
            continue

        try:
            num_val = float(value)
            if num_val == int(num_val):
                num_val = int(num_val)
        except ValueError:
            num_val = value.strip()

        if key in attr_mapping:
            name, target = attr_mapping[key]
            target[name] = num_val
        elif key in combat_mapping:
            name, target = combat_mapping[key]
            target[name] = num_val
        elif key in defense_mapping:
            name, target = defense_mapping[key]
            target[name] = num_val
        elif key in offense_mapping:
            name, target = offense_mapping[key]
            target[name] = num_val
        elif key in power_mapping:
            name, target = power_mapping[key]
            target[name] = num_val
        elif key in stat_mapping:
            name, target = stat_mapping[key]
            target[name] = num_val
        elif key in body_parts:
            name, target = body_parts[key]
            target[name] = num_val
        elif key in flags:
            name, target = flags[key]
            target[name] = num_val
        elif key in ["weapon", "armor"]:
            offense[key] = value.strip()
        elif key not in [
            "name",
            "Tier",
            "ID",
            "type",
            "faction",
            "pattern",
            "category1",
            "category2",
            "size",
            "matter",
            "Checksum",
            "",
            "achievement",
            "trophy",
            "Threat_Time",
        ]:
            other[key] = num_val

    result = {}
    if attributes:
        result["attributes"] = attributes
    if combat:
        result["combat"] = combat
    if defense:
        result["defense"] = defense

    if offense:
        damage_types = {}
        regular_fields = {}
        for k, v in offense.items():
            if k in [
                "slashing",
                "piercing",
                "blunt",
                "rending",
                "fire",
                "shock",
                "poison",
                "caustic",
                "frost",
                "arcane",
                "unholy",
                "sacred",
                "psionic",
            ]:
                damage_types[k] = v
            else:
                regular_fields[k] = v

        if damage_types:
            regular_fields["damageTypes"] = damage_types
        result["offense"] = regular_fields

    if resistances:
        result["resistances"] = resistances
    if other:
        result["other"] = other

    return result


def get_difficulty(tier: int, category: str) -> str:
    """根据等级和分类判断难度"""
    if tier == 0:
        return "trivial"
    elif tier == 1:
        return "easy"
    elif tier == 2:
        return "medium"
    elif tier == 3:
        return "hard"
    elif tier == 4:
        return "elite"
    elif tier >= 5:
        return "boss"
    return "medium"


def generate_search_keywords(
    name_en: str, name_zh: str, faction: str, mob_type: str, pattern: str, category: str
) -> List[str]:
    """生成搜索关键词"""
    keywords = []

    if name_en:
        keywords.append(name_en.lower())
    if name_zh:
        keywords.append(name_zh)
    if faction:
        keywords.append(faction.lower())
    if mob_type:
        keywords.append(mob_type.lower())
    if pattern:
        keywords.append(pattern.lower())
    if category:
        keywords.append(category.lower())

    return list(set(keywords))


def step6_convert_mobs_to_json(cfg: Config) -> bool:
    log_step(6, 6, "转换为怪物 JSON 格式")

    mobs_stats_file = cfg.extracted_dir / "mobs_stats.csv"
    if not mobs_stats_file.exists():
        log_error("找不到 mobs_stats.csv")
        return False

    name_translations, desc_translations = parse_mobs_translations(cfg)

    mobs_dir = cfg.json_dir / "mobs"
    if mobs_dir.exists():
        shutil.rmtree(mobs_dir)
    mobs_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    factions = set()
    tiers = set()

    with open(mobs_stats_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mob_key = row.get("name", "").strip()
            if not mob_key or mob_key.startswith("//") or mob_key.startswith("["):
                continue

            mob_id = row.get("ID", "").strip() or to_kebab_case(mob_key)
            tier = safe_int(row.get("Tier", "0").strip(), 0)
            faction = row.get("faction", "").strip()
            mob_type = row.get("type", "").strip()
            pattern = row.get("pattern", "").strip()
            category1 = row.get("category1", "").strip()
            category2 = row.get("category2", "").strip()
            size = row.get("size", "").strip()
            matter = row.get("matter", "").strip()

            trans_key = mob_id if mob_id in name_translations else mob_key
            name_trans = name_translations.get(trans_key, {})
            desc_trans = desc_translations.get(trans_key, {})

            name_en = name_trans.get("en", mob_key)
            name_zh = name_trans.get("zh", "")
            desc_en = desc_trans.get("en", "")
            desc_zh = desc_trans.get("zh", "")

            difficulty = get_difficulty(tier, category1)
            keywords = generate_search_keywords(
                name_en, name_zh, faction, mob_type, pattern, category1
            )

            tags = []
            if mob_type:
                tags.append(mob_type)
            if pattern:
                tags.append(pattern)
            if category1:
                tags.append(category1)
            if category2:
                tags.append(category2)

            data = {
                "id": mob_id,
                "name": {"en": name_en, "zh": name_zh},
                "tier": tier,
                "faction": faction,
                "type": mob_type,
                "display": {
                    "difficulty": difficulty,
                    "tags": list(set(tags)),
                    "keywords": keywords,
                },
            }

            if size:
                data["size"] = size
            if matter:
                data["matter"] = matter

            if desc_en or desc_zh:
                data["description"] = {"en": desc_en, "zh": desc_zh}

            categorized_stats = categorize_mob_stats(row)
            if categorized_stats:
                data.update(categorized_stats)

            file_name = mob_id if mob_id else to_kebab_case(name_en)
            if len(file_name) > 100:
                file_name = file_name[:100]
            json_path = mobs_dir / f"{file_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            count += 1
            factions.add(faction)
            tiers.add(str(tier))

    log_success(f"怪物: {count} 个，分布在 {len(factions)} 个阵营")

    generate_mobs_index(cfg, count, factions, tiers)

    return count > 0


def generate_mobs_index(cfg: Config, count: int, factions: set, tiers: set):
    """生成怪物索引文件"""
    index = {
        "version": cfg.version,
        "count": count,
        "factions": sorted(factions),
        "tiers": sorted(tiers),
    }

    index_path = cfg.json_dir / "mobs" / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    log_success(f"怪物索引: {index_path}")


# ============================================================================
# Main Pipeline
# ============================================================================
STEP_NAMES = {
    "1": 0,
    "unpack": 0,
    "2": 1,
    "strings": 1,
    "3": 2,
    "tables": 2,
    "4": 3,
    "sprites": 3,
    "5": 4,
    "json": 4,
    "6": 5,
    "mobs": 5,
}

STEPS = [
    ("解包 data.win", step1_unpack),
    ("提取字符串资源", step2_extract_strings),
    ("提取 Table 数据", step3_extract_tables),
    ("提取 Sprite 图片", step4_extract_sprites),
    ("转换为 JSON", step5_convert_to_json),
    ("提取怪物数据", step6_convert_mobs_to_json),
]


def parse_step_spec(spec: str) -> List[int]:
    selected = set()
    for part in spec.split(","):
        part = part.strip().lower()
        if "-" in part and len(part.split("-")) == 2:
            a, b = part.split("-")
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
        weapon_slots = (
            [d for d in weapons_dir.iterdir() if d.is_dir()]
            if weapons_dir.exists()
            else []
        )
        armor_slots = (
            [d for d in armor_dir.iterdir() if d.is_dir()] if armor_dir.exists() else []
        )
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
