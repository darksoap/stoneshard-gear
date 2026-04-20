# Stoneshard Gear

Stoneshard（紫色晶石）游戏装备图鉴。

## 项目结构

```
src/
├── content/          # 装备数据
│   ├── weapons/
│   └── armor/
├── components/       # UI 组件
├── i18n/             # 中英文属性映射
├── layouts/          # 页面布局
└── pages/            # 路由页面
```

## 开发

```sh
npm install
npm run dev        # http://localhost:4321
npm run build      # 输出到 ./dist/
```

## 数据清洗管线

游戏数据通过 Python Pipeline 从 data.win 自动提取：

```
scripts/
├── extract_pipeline.py      # 主 Pipeline：解包 → 提取 → 合并 → 输出 JSON
└── dataTemplate/
    ├── weapon.csv           # 武器字段映射模板
    ├── armor.csv            # 护甲字段映射模板
    └── enemy.csv            # 敌人字段映射模板（预留）
```

**Pipeline 流程：**
1. **解包** — 使用 UTMT-CLI 从 data.win 解包 GML 脚本和精灵图
2. **提取** — 解析 GML 代码，提取物品基础属性、图标、描述
3. **合并** — 将 items_stats 中的额外属性合并到主数据
4. **分类** — 按 slot 自动分类存放（weapons/helmets/chests 等）
5. **变种处理** — 重甲头盔变种合并到单个文件

**使用：**
```bash
# 完整流程（需配置 game_data 路径）
python scripts/extract_pipeline.py --all

# 单独运行某阶段
python scripts/extract_pipeline.py --step extract  # 仅提取
python scripts/extract_pipeline.py --step export   # 仅导出 JSON
```
