# 定期タスクの手順（美術ブログ「一枚の名画から」）

リポジトリは boiledtomato/meiga-note、ブランチは main。美術以外の話題は書かないこと。

1. `git checkout main && git pull origin main` と `pip install -q -r requirements.txt`
2. `python3 scripts/blog_sources.py today` で今日のブリーフを取得。「何もしないで終了」と出たら今日は休み。
3. `WRITING_RULES.md` と `WRITING_GUIDE.md` を読み、ルールに厳密に従って記事を1本書く。
   - art-artwork：ブリーフの作品データと所蔵館ページを根拠に書く。画像はブリーフの「画像(小)」URL を使う。
     所蔵館ページが開けないときは Met の API（collectionapi.metmuseum.org）と画像そのものを根拠にし、確認できない細部は「要確認」と書く。
   - art-topic：ブリーフのテーマで書く。細部は公式情報で確認できたものだけを書く。
   - 保存先は `content/posts/<今日の日付>-<topic_id>.md`。
4. 本文の文字数を数え、2,500〜4,000 文字に収まっているか確かめる。
5. `python3 scripts/build_site.py --check` が OK になるまで修正し、`python3 scripts/build_site.py` を実行（REPORT.md が更新される）。
6. 記事を書いた場合のみ `git add content/ data/ REPORT.md && git commit -m "blog: <日付> <記事タイトル>"` して `git push origin main`。
   リモートが進んでいたら `git pull --rebase origin main` してから push。
7. push 後、公開URL が HTTP 200 を返すまで最大5分待って確認する。
8. 報告は1行：記事タイトルと公開URL（https://boiledtomato.github.io/meiga-note/posts/<ファイル名から .md を除いたもの>/）、または「休み」。
