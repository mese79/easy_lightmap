import os
import bpy

from bpy.props import StringProperty, BoolProperty, IntProperty
from subprocess import Popen, PIPE


bl_info = {
    "name": "Easy Light Map",
    "author": "Mehdi Seifi",
    "version": (0, 1),
    "blender": (2, 73),
    "location": "Render Tab > Easy Light Map",
    "description": "Bakes light map for selected object easily!",
    "warning": "",
    "wiki_url": "https://github.com/mese79/easy_lightmap",
    "category": "Render"
}


class EasyLightMapProperties(bpy.types.PropertyGroup):
    
    bake_path = StringProperty(name="Bake folder:", default="", subtype="DIR_PATH", description="Path for saving baked maps.")
    image_w = IntProperty(name="Width", default=1024, min=1, description="Image width")
    image_h = IntProperty(name="Height", default=1024, min=1, description="Image height")
    check_uv = BoolProperty(name="Check/Create UV Layers", default=True, description="Create two uv layers if there is not any.")
    bake_diffuse = BoolProperty(name="Bake diffuse color", default=False, description="Bake material diffuse color into map.")
    bake_textures = BoolProperty(name="Bake textures", default=False, description="Bake material textures into map.")


class EasyLightMap(bpy.types.Operator):

    """ Main operation happens here. """
    bl_idname = "object.easy_light_map"
    bl_label = "Bake It!"
    bl_description = "Bake light map into new texture and add it into object material."

    settings = None
    selected_object = None
    material = None
    textures_use = []

    @classmethod
    def poll(cls, context):
        if context.scene.render.engine == "BLENDER_RENDER":
            return True

    def execute(self, context):
        print("\ncontext.object:", context.object)
        self.selected_object = context.active_object
        if self.selected_object is None or self.selected_object.type != "MESH":
            self.report({"WARNING"}, "No mesh object was selected.")
        
        self.material = self.selected_object.active_material

        self.settings = context.scene.easyLightMap

        self.get_used_textures()
        self.check_uv_layers()

        # Add new texture slot and new image for baking.
        name = "Baked_" + self.material.name
        
        img_path = bpy.path.abspath(self.settings.bake_path)
        if not img_path:
            img_path = bpy.path.abspath("//")
        img_path = os.path.join(img_path, name + ".png")
        
        img = bpy.data.images.get(name)
        if img is None:
            img = bpy.data.images.new(name, width=self.settings.image_w, height=self.settings.image_h, alpha=True)
            img.file_format = "PNG"
            img.filepath = img_path
        elif img.size != [self.settings.image_w, self.settings.image_h]:
            img.scale(self.settings.image_w, self.settings.image_h)

        baked_tex = bpy.data.textures.get(name)
        if baked_tex is None:
            baked_tex = bpy.data.textures.new(name, type="IMAGE")
        baked_tex.image = img
        baked_tex.use_alpha = True
        
        baked_slot = self.material.texture_slots.get(name)
        if baked_slot is None:
            baked_slot = self.material.texture_slots.add()
        baked_slot.use = False
        baked_slot.texture = baked_tex
        baked_slot.texture_coords = "UV"
        baked_slot.uv_layer = self.selected_object.data.uv_textures.active.name

        # Bake It
        uv_layer = self.selected_object.data.uv_textures.active
        for uv in uv_layer.data:
            uv.image = baked_tex.image

        bpy.ops.object.bake_image()
        img.save()

        # Removing diffuse color
        if not self.settings.bake_diffuse:
            self.remove_diffuse_color(img_path)

        # Revert back texture_slots.use check boxes.
        for index in range(len(self.textures_use)):
            if self.material.texture_slots[index] is not None:
                self.material.texture_slots[index].use = self.textures_use.pop(0)

        # Use new baked texture
        img.reload()
        baked_slot.use = True
        baked_slot.blend_type = "MULTIPLY"

        # Done!
        return {"FINISHED"}

    def get_used_textures(self):
        """ UnCheck textures if bake_textures is false. """
        for slot in self.material.texture_slots:
            if slot is not None and slot.use:
                self.textures_use.append(slot.use)
                if not self.settings.bake_textures:
                    slot.use = False

    def check_uv_layers(self):
        """ Object must have two uv sets. """
        if len(self.selected_object.data.uv_textures) == 0:
            self.add_uv_map("Diffuse")
            self.add_uv_map("LightMap")
        elif len(self.selected_object.data.uv_textures) == 1:
            self.add_uv_map("LightMap")

    def add_uv_map(self, name):
        """ Add new UV Map to object and unwrap it. """
        uv = self.selected_object.data.uv_textures.new(name)
        uv.active = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.05)
        # Have to pass object, because context.object is None in render panel.
        # (in unwrap function is_editmode = (context.object.mode == 'EDIT') will need it.)
        #bpy.ops.uv.lightmap_pack({
        #                          "object": self.selected_object,
        #                          "PREF_CONTEXT": "ALL_OBJECTS",
        #                          "PREF_PACK_IN_ONE": True,
        #                          "PREF_IMG_PX_SIZE": self.settings.image_w
        #                         })
        bpy.ops.object.mode_set(mode="OBJECT")
        uv.active = True

        return uv

    def remove_diffuse_color(self, file):
        """ Remove diffuse color by ImageMagick. """
        params = [
            "mogrify", "-normalize", "-grayscale", "Rec709Luma",
            "-type", "TrueColorMatte", "-define", "png:color-type=6", file
        ]
        process = Popen(params, stdin=PIPE, stdout=PIPE)
        out, err = process.communicate()


class EasyLightMapPanel(bpy.types.Panel):

    bl_idname = "RENDER_PT_easy_light_map"
    bl_label = "Easy Light Map"
    bl_region_type = "WINDOW"
    bl_space_type = "PROPERTIES"
    bl_context = "render"

    @classmethod
    def poll(cls, context):
        if context.scene.render.engine == "BLENDER_RENDER":
            return True

    def draw(self, context):
        layout = self.layout
        props = context.scene.easyLightMap
        row = layout.row(True)
        row.prop(props, "bake_path")
        row = layout.row(True)
        row.prop(props, "image_w")
        row.prop(props, "image_h")
        layout.separator()
        row = layout.row(True)
        row.prop(props, "check_uv")
        row = layout.row(True)
        row.prop(props, "bake_diffuse")
        row = layout.row(True)
        row.prop(props, "bake_textures")
        layout.separator()
        layout.operator(EasyLightMap.bl_idname, text="Bake it!")


def register():
    bpy.utils.register_class(EasyLightMapProperties)
    bpy.types.Scene.easyLightMap = bpy.props.PointerProperty(type=EasyLightMapProperties)
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)


if __name__ == '__main__':
    register()
