import bpy

class HOLOGRAM_PT_Panel(bpy.types.Panel):
    bl_label = "Holographic Viewport"
    bl_idname = "HOLOGRAM_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Hologram"

    def draw(self, context):
        layout = self.layout
        props = context.scene.hologram_view_props

        col = layout.column(align=True)

        # Toggle Button
        icon = "PAUSE" if props.is_active else "PLAY"
        text = "Stop Head Tracking" if props.is_active else "Start Head Tracking"
        col.operator("hologram.toggle", text=text, icon=icon)

        if props.is_active:
            box = layout.box()
            box.prop(props, "smoothing", slider=True)
            box.prop(props, "sensitivity")

def register():
    bpy.utils.register_class(HOLOGRAM_PT_Panel)

def unregister():
    bpy.utils.unregister_class(HOLOGRAM_PT_Panel)
