"""labnote のデータモデル。

設計方針:
- 実験の精度は「学習段階 × クラス区分 × 補正 × 指標(GZSL/ZSL)」の組み合わせで変わるため、
  固定列にはせず MetricDefinition（定義）＋ MetricValue（値）として持つ。評価項目は実験の進行に合わせて後から追加・変更できる。
- 補正は「なし / component fusion のみ / component fusion + calibrated stacking」の3値で表す。
  ZSL では calibrated stacking を適用できないことは、値の持ち方（補正の組に対して
  GZSL と ZSL の両方を記録する）と取り込み時の検証で表現する。
- 数値以外の記録（背景・変更点・考察・条件）は自由記述やキー/値の形で持ち、
  Googleドキュメントのような自由さを損なわないようにする。
"""
from django.db import models


class Experiment(models.Model):
    """実験1件。Googleドキュメントの「実験タブ」に相当する単位。"""

    code = models.CharField("実験ID", max_length=32, unique=True,
                            help_text="例: 261109（日付ベースのID）")
    title = models.CharField("タイトル", max_length=200)
    date = models.DateField("日付")
    # 背景・変更点・考察などの自由記述（Markdown想定）
    background = models.TextField("背景・問題意識", blank=True)
    changes = models.TextField("変更点", blank=True)
    discussion = models.TextField("結果の考察", blank=True)
    memo = models.TextField("メモ", blank=True)
    # 実験条件（クラス数・サンプル数など）。キー/値の自由な辞書。
    conditions = models.JSONField("実験条件", default=dict, blank=True)
    # 任意の学習パラメータ（ハイパーパラメータ等）。キー/値の自由な辞書。
    params = models.JSONField("学習パラメータ", default=dict, blank=True)
    git_commit = models.CharField("実験コードのGitコミット", max_length=64, blank=True)
    checkpoint = models.CharField("チェックポイントのパス", max_length=300, blank=True)
    tags = models.CharField("タグ", max_length=300, blank=True,
                            help_text="カンマ区切り")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "code"]
        verbose_name = "実験"
        verbose_name_plural = "実験"

    def __str__(self):
        return f"{self.code} {self.title}"

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class MetricDefinition(models.Model):
    """評価項目（指標）の定義。項目は固定ではなく、ここに追加していく。

    実験の取り込み時に未知のキーが現れたら自動で登録される。
    表示名・グループ・単位・並び順は後から画面で変更できる。
    """

    key = models.CharField("キー", max_length=200, unique=True,
                           help_text="例: pretrain_casia.unknown.component_calibrated.gzsl / val_loss など")
    label = models.CharField("表示名", max_length=300, blank=True,
                             help_text="空ならキーそのまま表示")
    group = models.CharField("表示グループ", max_length=100, blank=True,
                             help_text="例: 事前学習 (CASIA)")
    unit = models.CharField("単位", max_length=16, default="%", blank=True)
    sort_order = models.IntegerField("並び順", default=0)
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["group", "sort_order", "key"]
        verbose_name = "評価項目の定義"
        verbose_name_plural = "評価項目の定義"

    def __str__(self):
        return self.label or self.key

    @property
    def display_label(self):
        return self.label or self.key


class MetricValue(models.Model):
    """実験における評価項目1つの値。項目の定義は MetricDefinition 側で可変に持つ。"""

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE,
                                   related_name="values", verbose_name="実験")
    definition = models.ForeignKey(MetricDefinition, on_delete=models.PROTECT,
                                   related_name="values", verbose_name="評価項目")
    value = models.FloatField("値")
    note = models.CharField("注記", max_length=200, blank=True)

    class Meta:
        ordering = ["definition__group", "definition__sort_order", "definition__key"]
        unique_together = ["experiment", "definition"]
        verbose_name = "評価値"
        verbose_name_plural = "評価値"

    def __str__(self):
        return f"{self.experiment.code} / {self.definition.key} = {self.value}"


class Note(models.Model):
    """自由記述のノート。ドキュメントの「アイデア」「学び」タブや日誌に相当。"""

    class Kind(models.TextChoices):
        JOURNAL = "journal", "研究日誌"
        IDEA = "idea", "アイデア"
        LEARNING = "learning", "学び"
        FREE = "free", "自由メモ"

    kind = models.CharField("種類", max_length=16, choices=Kind.choices,
                            default=Kind.JOURNAL)
    title = models.CharField("タイトル", max_length=200)
    date = models.DateField("日付")
    body = models.TextField("本文 (Markdown)")
    experiment = models.ForeignKey(Experiment, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="notes",
                                   verbose_name="関連する実験")
    tags = models.CharField("タグ", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "ノート"
        verbose_name_plural = "ノート"

    def __str__(self):
        return f"{self.date} {self.title}"


class Reading(models.Model):
    """読んだ論文・本の感想とメモ。書誌情報はAPIで補完する想定。"""

    class ItemType(models.TextChoices):
        PAPER = "paper", "論文"
        BOOK = "book", "本"

    item_type = models.CharField("種別", max_length=8, choices=ItemType.choices)
    title = models.CharField("タイトル", max_length=400)
    authors = models.CharField("著者", max_length=400, blank=True)
    year = models.PositiveIntegerField("年", null=True, blank=True)
    venue = models.CharField("掲載誌・学会 / 出版社", max_length=300, blank=True)
    doi = models.CharField("DOI", max_length=120, blank=True)
    isbn = models.CharField("ISBN", max_length=32, blank=True)
    url = models.URLField("URL", blank=True)
    cover_url = models.URLField("表紙画像URL", blank=True)
    read_date = models.DateField("読んだ日", null=True, blank=True)
    rating = models.PositiveSmallIntegerField("評価 (1-5)", null=True, blank=True)
    summary = models.TextField("要約", blank=True)
    impression = models.TextField("感想・メモ", blank=True)
    tags = models.CharField("タグ", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-read_date", "-created_at"]
        verbose_name = "読書記録"
        verbose_name_plural = "読書記録"

    def __str__(self):
        return self.title


class Attachment(models.Model):
    """実験・ノート・読書記録に添付する画像など（ロス推移グラフ等）。"""

    image = models.ImageField("画像", upload_to="attachments/%Y/%m/")
    caption = models.CharField("説明", max_length=300, blank=True)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE,
                                   null=True, blank=True, related_name="attachments",
                                   verbose_name="実験")
    note = models.ForeignKey(Note, on_delete=models.CASCADE,
                             null=True, blank=True, related_name="attachments",
                             verbose_name="ノート")
    reading = models.ForeignKey(Reading, on_delete=models.CASCADE,
                                null=True, blank=True, related_name="attachments",
                                verbose_name="読書記録")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "添付画像"
        verbose_name_plural = "添付画像"

    def __str__(self):
        return self.caption or (self.image.name if self.image else "")
