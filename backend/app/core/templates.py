from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

# autoescape off: these render plain-text email bodies, not HTML.
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape(enabled_extensions=()))


def render_template(name: str, **context) -> str:
    return jinja_env.get_template(name).render(**context)
