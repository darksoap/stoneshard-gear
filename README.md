# Stoneshard Gear

Stoneshard（紫色晶石）游戏装备图鉴。

在线预览：[装备图鉴](https://darksoap.github.io/stoneshard-gear/)

## 开发

```sh
bun install
bun run dev        # http://localhost:4321
bun run build      # 输出到 ./dist/
```

## 数据来源

游戏数据通过 Python Pipeline 从 `data.win` 自动提取，存放于 `src/content/`。

```
scripts/
├── extract_pipeline.py      # 主 Pipeline：解包 → 提取 → 合并 → 输出 JSON
└── dataTemplate/
    ├── weapon.csv           # 武器字段映射模板
    └── armor.csv            # 护甲字段映射模板
```

**使用：**
```bash
python scripts/extract_pipeline.py --all
```
