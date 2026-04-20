# Stoneshard Compendium

Stoneshard（紫色晶石）游戏资料图鉴，基于 Astro + Tailwind CSS 构建，部署于 GitHub Pages。

## 项目结构

```
src/
├── content/          # 装备数据（JSON，由 Content Collections 管理）
│   ├── weapons/
│   ├── armor/
│   └── jewelry/
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

## 部署

推送到 `main` 分支后由 GitHub Actions 自动构建部署。

访问地址：`https://<username>.github.io/stoneshard-compendium/`
