import os
import streamlit.components.v1 as components

# Create a _RELEASE constant. We'll set this to False while we're developing
# the component, and True when we're ready to package and distribute it.
_RELEASE = True

if not _RELEASE:
    _component_func = components.declare_component(
        "editable_table",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    _component_func = components.declare_component("editable_table", path=parent_dir)

def editable_table(html_str, key=None):
    """
    Renders an HTML string containing <input class="editable-cell"> elements.
    Returns a dictionary when an input is edited, containing {'id': input_id, 'value': new_value}
    """
    component_value = _component_func(html=html_str, key=key, default=None)
    return component_value
