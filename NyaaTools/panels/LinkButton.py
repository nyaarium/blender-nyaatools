import webbrowser
import bpy
from bpy.props import StringProperty


class NYAATOOLS_OT_LinkButton(bpy.types.Operator):
    """Open links in a web browser"""

    bl_idname = "ops.open_link"
    bl_label = "Open Link in web browser"
    bl_options = {"REGISTER"}

    url: StringProperty(name="URL", description="URL", default="")

    def execute(self, context):
        webbrowser.open_new(self.url)  # opens in default browser
        return {"FINISHED"}
