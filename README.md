# 一枚の名画から

洞窟壁画から現代美術まで、名作を一枚ずつ読み解く美術史の学習ノート。

- 公開URL: https://boiledtomato.github.io/meiga-note/
- 更新日: 火・土（今日の一枚）・木・日（美術史）
- 作品画像はメトロポリタン美術館の Open Access（パブリックドメイン / CC0）のみ使用

## フォルダ構成

```
config.json             サイト名・URL・デザイン・広告ID・曜日スケジュール
WRITING_RULES.md        執筆ルール
WRITING_GUIDE.md        記事タイプごとの執筆ガイド
SCHEDULED_TASK_PROMPT.md 定期タスクの手順
content/posts/          記事（Markdown）
data/topics.json        美術史テーマの在庫（上から順に使う）
data/revenue.json       売上の記録
data/costs.json         コストの記録
REPORT.md               記事数・売上・コスト・収支（自動更新）
scripts/blog_sources.py 今日の記事タイプと材料（Met API から作品を選ぶ）
scripts/build_site.py   静的サイトを _site/ に生成
```

push すると GitHub Actions（.github/workflows/pages.yml）がビルドして GitHub Pages に公開します。

2026-11-11 に boiledtomato/zscaler-monitor から分離しました（旧URL https://boiledtomato.github.io/zscaler-monitor/art/ からは転送）。
