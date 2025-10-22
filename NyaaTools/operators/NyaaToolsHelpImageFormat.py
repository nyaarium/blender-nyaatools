import bpy
import traceback


help_text = """--==[ DTP Format Guide ]==--

EXAMPLES:
Color RGB:   image.rgb.jpg
Color RGBA:   image.rgba.png
Normal Map OpenGL:   image.normalgl.jpg
Plain AO Map:   image.ao.png
Plain Roughness Map:   image.ro.png
Emission:   image.emission.jpg
Unity URP:   image.me-00-00-sm.png
Unreal ORM:   image.ao-ro-me.png
PBR w/Spec:   image.me-ro-sm.jpg
PBR w/AO:   image.me-ro-ao.png
PBR for Voices of the Void:   image.me-sp-ro.png

ALIASES:
*.rgb.*   →   cr-cg-cb (sRGB Color)
*.rgba.*   →   cr-cg-cb-al (sRGB Color with Alpha)
*.linear.*   →   lr-lg-lb (Linear Color)
*.lineara.*   →   lr-lg-lb-al (Linear Color with Alpha)
*.emission.*   →   er-eg-eb-es (Emission map)
*.normalgl.*   →   nx-ng (Normal map OpenGL)
*.normaldx.*   →   nx-nd (Normal map DirectX)

CHANNEL CODES:
00 = Unused channel
cr = sRGB Color (red)
cg = sRGB Color (green)
cb = sRGB Color (blue)
lr = Linear Color (red)
lg = Linear Color (green)
lb = Linear Color (blue)
al = Alpha
nx = Normal X
ng = Normal +Y (OpenGL)
nd = Normal -Y (DirectX)
he = Height
me = Metallic
sp = Specular
ro = Roughness
sm = Smoothness
ao = Ambient Occlusion
er = Emission (red)
eg = Emission (green)
eb = Emission (blue)
es = Emission Strength"""


class NyaaToolsHelpImageFormat(bpy.types.Operator):
    """Display help about DTP image format naming convention"""

    bl_idname = "nyaa.help_image_formats"
    bl_label = "Help: Image Formats"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            self.report({"ERROR"}, help_text)
            return {"CANCELLED"}  # Using CANCELLED to force the error display

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
