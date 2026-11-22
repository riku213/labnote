# labnote

研究の実験管理・記録ダッシュボード。くずし字認識の研究を対象に、実験結果の構造化記録と、自由記述のノート（進捗・アイデア・学び・日誌）、論文・本の読書メモを一か所で管理する。

## 特徴（予定を含む）
- 実験結果は、Copilot等に指示して出力させた YAML ファイル（`result.yaml`）をアップロードして取り込める
- 指標は「学習段階 × 既知/未知クラス × 補正の有無 × GZSL/ZSL」の組み合わせで記録し、実験同士を比較できる
- 実験やノートには画像（ロス推移グラフなど）を添付できる
- 記録は SQLite に保存し、Google Drive へ人間が読める Markdown 形式で書き出せる

## セットアップ
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## 実験結果ファイル（result.yaml）の形式
`docs/result_yaml.md` を参照。

## 注意
このリポジトリは公開前提です。APIキーや研究データ本体は `.gitignore` で除外しています。秘密情報は絶対にコミットしないでください。

## APIキー（任意）

キーなしでも動きます（論文検索は Crossref、本の検索は国立国会図書館サーチへ自動で切り替わります）。ただし共有IP等で無償枠を使い切ると検索が不安定になるため、自分のキーを登録すると安定します。

1. `.env.example` を `.env` にコピーする（`.env` は .gitignore 済みで、GitHubには上がりません）
2. 取得したキーを `.env` に書く
   - OpenAlex: https://openalex.org/settings/api （アカウント登録後に発行）
   - Google Books: Google Cloud Console でプロジェクトを作り、「Books API」を有効化して「認証情報」からAPIキーを作成
3. アプリを再起動する

キーをチャットやGitHubに貼らないでください。
