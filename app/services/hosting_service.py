from pathlib import Path
from PIL import Image, ImageDraw


def _css_from_props(props):
    mapping = {
        "font_family": "font-family",
        "font_size": "font-size",
        "font_weight": "font-weight",
        "color": "color",
        "text_align": "text-align",
        "line_height": "line-height",
        "letter_spacing": "letter-spacing",
        "background_color": "background-color",
        "background_image": "background-image",
        "border_radius": "border-radius",
        "padding_x": "padding-left",
        "padding_y": "padding-top",
        "object_fit": "object-fit",
        "width": "width",
        "height": "height",
    }
    css = []
    for k, v in props.items():
        if v is None:
            continue
        key = mapping.get(k)
        if key:
            css.append(f"{key}:{v}")
    return ";".join(css)


def render_element(element):
    etype = element.get("type")
    props = element.get("props", {})
    style = _css_from_props(props)
    if etype == "heading":
        tag = props.get("tag", "h2")
        return f"<{tag} style='{style}'>{props.get('text', '')}</{tag}>"
    if etype == "paragraph":
        return f"<p style='{style}'>{props.get('text', '')}</p>"
    if etype == "button":
        target = "_blank" if props.get("open_in_new_tab") else "_self"
        return f"<a href='{props.get('href', '#')}' target='{target}' style='{style};display:inline-block'>{props.get('text','Click')}</a>"
    if etype == "image":
        return f"<img src='{props.get('src','')}' alt='{props.get('alt','')}' style='{style}'/>"
    if etype == "form":
        fields_html = "".join([f"<input placeholder='{f.get('placeholder','')}' {'required' if f.get('required') else ''}/>" for f in props.get("fields", [])])
        return f"<form>{fields_html}<button>{props.get('submit_button_text', 'Submit')}</button></form>"
    if etype in {"testimonial_card", "pricing_card", "team_card", "gallery_grid"}:
        return f"<div class='card' style='{style}'>{props}</div>"
    return f"<div style='{style}'>{props}</div>"


def render_page(site, page, pages):
    sections = sorted(page.sections or [], key=lambda s: s.get("order", 0))
    body_parts = []
    for section in sections:
        if not section.get("is_visible", True):
            continue
        settings = section.get("settings", {})
        section_style = _css_from_props(settings)
        elements = sorted(section.get("elements", []), key=lambda e: e.get("order", 0))
        rendered = "".join(render_element(el) for el in elements)
        body_parts.append(f"<section id='{section.get('id')}' class='{section.get('type')}' style='{section_style}'>{rendered}</section>")

    nav_links = "".join([f"<a href='/{p.slug if not p.is_homepage else ''}'>{p.name}</a>" for p in sorted(pages, key=lambda x: x.order)])
    gs = site.global_styles or {}
    fonts = gs.get("fonts", ["Inter"])
    font_import = "|".join(fonts).replace(" ", "+")
    return f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>{site.meta_title or site.name}</title>
<meta name='description' content='{site.meta_description or ''}'/>
<link rel='icon' href='{site.favicon_url or ''}'/>
<link href='https://fonts.googleapis.com/css2?family={font_import}:wght@400;600;700&display=swap' rel='stylesheet'/>
<style>:root{{--font-primary:{fonts[0]};--color-primary:{gs.get('colors',{}).get('primary','#111827')};--color-bg:{gs.get('colors',{}).get('background','#ffffff')}}}body{{font-family:var(--font-primary);background:var(--color-bg);}}</style>
</head>
<body><nav>{nav_links}</nav>{''.join(body_parts)}</body>
</html>"""


def deploy_site_output(site, pages):
    out_dir = Path("generated_sites") / str(site.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        html = render_page(site, page, pages)
        filename = "index.html" if page.is_homepage else f"{page.slug}.html"
        (out_dir / filename).write_text(html, encoding="utf-8")

    img = Image.new("RGB", (1200, 630), color=(17, 24, 39))
    draw = ImageDraw.Draw(img)
    draw.text((40, 300), f"{site.name} published", fill=(255, 255, 255))
    img.save(out_dir / "screenshot.png")
    return out_dir
