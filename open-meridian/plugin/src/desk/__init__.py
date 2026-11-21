"""A read-only trading desk as an Open Meridian `reporting` plugin.

The wrapper serves a docking layout of panels (Dockview's MIT packages) on
the plugin's page, and answers each panel's read through the plugin's
sidecar: the book's orders, placements, fills and positions, cut to the
accounts of the person whose page it is, and the lake's latest prices and
bars, for the instrument picked. It keeps nothing and takes no order act.
"""
