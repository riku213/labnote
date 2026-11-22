# 実験結果ファイル（result.yaml）の仕様

実験コードの実行結果を labnote に取り込むための形式です。
実験が終わったら、この形式の `result.yaml` を1ファイル出力し、labnote の
「YAML取り込み」画面からアップロードしてください。取り込み時に形式チェックを行い、
内容のプレビューを確認してから保存します。

## 形式

```yaml
experiment:
  code: "261109"          # 必須。実験ID（日付ベース等、一意な文字列）
  title: "592ビット固定"   # 必須
  date: 2026-11-09        # 必須
  changes: "変更点の自由記述"        # 任意
  background: "背景・問題意識"       # 任意
  discussion: "結果の考察"          # 任意
  memo: "メモ"                      # 任意
  git_commit: "abc1234"             # 任意
  checkpoint: "runs/261109/best.pth" # 任意（パス文字列のみ。実ファイルは含めない）
  tags: "固定ビット, codebook"       # 任意（カンマ区切り、またはリスト）
conditions:               # 任意。クラス数・サンプル数など。キー/値自由
  known_classes: "2568 / 4285"
  samples: 27484
params:                   # 任意。学習パラメータ。キー/値自由
  lr: 0.001
  epochs: 50
results:                  # 精度。組み合わせごとに1要素
  - stage: pretrain_casia       # pretrain_casia | finetune_kuzushiji
    class_type: unknown         # known | unknown
    correction: component_calibrated  # none | component | component_calibrated
    gzsl: 58.08                 # 任意（0〜100）。zslとどちらか一方は必須
    zsl: 62.11                  # 任意（0〜100）
    note: ""                    # 任意。値への注記
```

## 補正（correction）の意味と注意

- `none`: 補正なし
- `component`: bag-of-component による component fusion のみ
- `component_calibrated`: component fusion + calibrated stacking

calibrated stacking は ZSL には適用できません。そのため補正の値に
「calibrated stacking のみ」は存在しません。`component_calibrated` の行の
`zsl` は「component fusion を適用した ZSL の精度（calibrated stacking は
適用されていない）」を表します。これは従来の手書き表で
「component (+ calibrated)」列に GZSL と ZSL を並べて書いていた運用と同じ意味です。

## Copilotへの指示文（例）

実験コードを GitHub Copilot と開発している場合、次のような指示で
学習・評価スクリプトに result.yaml の出力を組み込めます。

> このリポジトリの評価が終わるタイミングで、labnote の仕様
> （docs/result_yaml.md）に沿った result.yaml を実行ディレクトリに出力する処理を追加してください。
> experiment.code は実行日の日付から作る実験ID、results には
> stage（pretrain_casia / finetune_kuzushiji）× class_type（known / unknown）×
> correction（none / component / component_calibrated）の各組み合わせについて
> GZSL と ZSL の精度（%）を入れてください。値が無い組み合わせは要素ごと省略してください。
> checkpoint には実ファイルではなくパスの文字列だけを入れてください。
