THEMES = ("standard", "material", "apple", "github", "dark",
          "dracula", "solarized", "washi", "terminal", "newspaper")
CARD_THEMES = {"material", "apple", "github", "dark", "dracula",
               "solarized", "washi", "terminal", "newspaper"}


def theme(request):
    value = request.COOKIES.get("labnote_theme", "standard")
    if value not in THEMES:
        value = "standard"
    return {"labnote_theme": value,
            "labnote_cards": "card" if value in CARD_THEMES else "flat"}
