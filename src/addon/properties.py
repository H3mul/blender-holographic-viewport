import bpy


class HologramViewportProperties(bpy.types.PropertyGroup):
    is_active: bpy.props.BoolProperty(name="Hologram View Active", description="Toggle head tracking", default=False)
    smoothing: bpy.props.FloatProperty(name="Smoothing", default=0.5, min=0.0, max=0.9)
    sensitivity: bpy.props.FloatProperty(name="Sensitivity", default=2.0)


def register():
    bpy.utils.register_class(HologramViewportProperties)
    bpy.types.Scene.hologram_view_props = bpy.props.PointerProperty(type=HologramViewportProperties)


def unregister():
    del bpy.types.Scene.hologram_view_props
    bpy.utils.unregister_class(HologramViewportProperties)
