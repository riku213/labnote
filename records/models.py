"""labnote のデータモデル。

設計方針:
- 実験の精度は「学習段階 × クラス区分 × 補正 × 指標(GZSL/ZSL)」の組み合わせで変わるため、
  固定列にはせず MetricResult として1行ずつ持つ。指標の組み合わせは後から増減できる。
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


class MetricResult(models.Model):
    """実験の精度1件。

    (学習段階, クラス区分, 補正) の組み合わせごとに GZSL / ZSL を持つ。
    値が無い組み合わせは行自体を作らない（sparse）。
    """

    class Stage(models.TextChoices):
        PRETRAIN = "pretrain_casia", "事前学習 (CASIA)"
        FINETUNE = "finetune_kuzushiji", "ファインチューニング (くずし字)"

    class ClassType(models.TextChoices):
        KNOWN = "known", "既知クラス"
        UNKNOWN = "unknown", "未知クラス"

    class Correction(models.TextChoices):
        NONE = "none", "補正なし"
        COMPONENT = "component", "component fusion のみ"
        COMPONENT_CALIBRATED = "component_calibrated", \
            "component fusion + calibrated stacking"

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE,
                                   related_name="metrics", verbose_name="実験")
    stage = models.CharField("学習段階", max_length=32, choices=Stage.choices)
    class_type = models.CharField("クラス区分", max_length=16, choices=ClassType.choices)
    correction = models.CharField("補正", max_length=32, choices=Correction.choices)
    gzsl = models.FloatField("GZSL精度(%)", null=True, blank=True)
    zsl = models.FloatField("ZSL精度(%)", null=True, blank=True)
    note = models.CharField("注記", max_length=200, blank=True,
                            help_text="例: CSなし、など値に付随する注記")

    class Meta:
        ordering = ["stage", "class_type", "correction"]
        unique_together = ["experiment", "stage", "class_type", "correction"]
        verbose_name = "指標結果"
        verbose_name_plural = "指標結果"

    def __str__(self):
        return (f"{self.experiment.code} / {self.get_stage_display()} / "
                f"{self.get_class_type_display()} / {self.get_correction_display()}")


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
