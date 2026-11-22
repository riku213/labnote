THEMES = ("standard", "material", "apple")


def theme(request):
    value = request.COOKIES.get("labnote_theme", "standard")
    if value not in THEMES:
        value = "standard"
    return {"labnote_theme": value}
