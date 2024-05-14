from django import template

from markdown import markdown
from django.utils.safestring import mark_safe


register = template.Library()

@register.filter(is_safe=True)
def render_markdown(value):
    """
    Render text as Markdown

    Example:
        {{ text | render_markdown }}
    """
    # Render Markdown
    html = markdown(value, extensions=["fenced_code", "tables"])

    return mark_safe(html)
