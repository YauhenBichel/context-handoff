"""One handler per hook event.

A handler takes the hook's event, the settings and the tool's adapter, and
returns the hook reply (a dict, a plain string, or None for no reply). It holds
the flow; measuring, deciding, notes and state live in their own modules, and
everything tool-specific comes from the adapter.
"""
