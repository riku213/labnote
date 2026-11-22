# 実験結果 YAML 仕様（v2）

GitHub Copilot に実験結果をこの形式で出力させ、labnote の「YAML取り込み」からアップロードすると、実験条件・パラメータ・評価値が構造化されて登録されます。

## 形式

```yaml
experiment:
  code: "261109"          # 実験ID（必須・一意）。同じIDで再取り込みすると更新される
  title: "実験タイトル"    # 必須
  date: 2026-11-09        # 必須（YYYY-MM-DD）
  git_commit: "abc1234"   # 任意
  checkpoint: "runs/xxx/best.pth"  # 任意
  tags: "構造部首, ゼロショット"     # 任意（カンマ区切り）
  background: |           # 任意
    背景・問題意識
  changes: |              # 任意
    前回からの変更点
  discussion: |           # 任意
    結果の考察
  memo: "自由メモ"         # 任意
conditions:               # 任意。実験条件（自由なキー・値）
  dataset: "くずし字"
  known_classes: 2568
params:                   # 任意。学習パラメータ（自由なキー・値）
  epochs: 50
  lr: 0.001
metrics:                  # 評価値のリスト（下記参照）
  - key: finetune_kuzushiji.known.none.gzsl
    value: 77.69
```

## 評価値（metrics）— 項目は固定ではありません

- `key`（必須）: 評価項目の識別子。英数字と `._-/` が使えます。**未知のキーは取り込み時に自動で評価項目として登録されます**。新しい評価軸（例: top-5 accuracy、検証ロス）が増えても、キーを増やすだけで対応できます。
- `value`（必須）: 数値。
- `label` / `group` / `unit`（任意）: 初回登録時の表示名・グループ名・単位（既定は %）。後から画面の「評価項目」ページでも変更できます。
- `note`（任意）: その値への注記。

### 現在の標準キー（くずし字OCR実験）

`<stage>.<class>.<correction>.<metric>` の形を推奨します。

- stage: `pretrain_casia`（事前学習） / `finetune_kuzushiji`（ファインチューニング）
- class: `known`（既知クラス） / `unknown`（未知クラス）
- correction: `none`（補正なし） / `component`（component fusion のみ） / `component_calibrated`（component fusion + calibrated stacking）
- metric: `gzsl` / `zsl`

注意: **ZSL に calibrated stacking は適用されません**。`component_calibrated` の ZSL の値は component fusion のみの値として扱ってください。

## 旧形式（v1）との互換

旧形式の `results:` リスト（stage / class_type / correction / gzsl / zsl）も引き続き取り込めます。内部で上記の標準キーに変換されます。

## Copilot への指示文（例）

> 実験が終わったら、結果を labnote の result YAML 形式（v2）で result_<実験ID>.yaml に出力してください。metrics のキーは <stage>.<class>.<correction>.<metric> の形式で、値は小数第2位まで。新しい評価項目を使った場合は metrics に新しいキーを追加し、label と group も書いてください。
