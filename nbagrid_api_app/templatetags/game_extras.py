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

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def filter_incorrect(players):
    """Filter a list of players to only include those where is_correct is False."""
    if not players:
        return []
    return [player for player in players if not player.get('is_correct', True)]

@register.filter
def get_correct_cell(cell_data_list):
    """Get the CellData object that has is_correct set to True."""
    if not cell_data_list:
        return None
    return next((cell_data for cell_data in cell_data_list if cell_data.get('is_correct', False)), None) 