from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return {}
    try:
        return dictionary.get(key, {})
    except (AttributeError, KeyError):
        return {} 