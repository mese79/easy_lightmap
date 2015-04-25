import os
import bpy

from bpy.props import StringProperty, BoolProperty, IntProperty
from bpy.app.handlers import persistent


bl_info = {
    "name": "Easy Light Map",
    "author": "Mehdi Seifi",
    "version": (0, 2),
    "blender": (2, 7),
    "location": "Render Tab > Easy Light Map",
    "description": "Bakes light map for selected object easily!",
    "warning": "",
    "wiki_url": "https://github.com/mese79/easy_lightmap",
    "category": "Render"
}


class General(object):
    
    is_baking_started = False
    original_color = None
    textures_use = []

    def __init__(self):
        pass


class EasyLightMapProperties(bpy.types.PropertyGroup):

    bake_path = StringProperty(
        name="Bake folder:", default="", subtype="DIR_PATH", description="Path for saving baked maps.")
    image_w = IntProperty(name="Width", default=1024, min=1, description="Image width")
    image_h = IntProperty(name="Height", default=1024, min=1, description="Image height")
    bake_diffuse = BoolProperty(name="Bake diffuse color", default=False, description="Bake material diffuse color into map.")
    bake_textures = BoolProperty(name="Bake textures", default=False, description="Bake material textures into map.")


class EasyLightMapPrepare(bpy.types.Operator):

    bl_idname = "object.easy_light_map_prepare"
    bl_label = "Only Prepare For Baking"
    bl_description = "Create two uv layers if there is not any then add an empty texture slot for baking."

    settings = None
    selected_object = None
    material = None

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        self.selected_object = context.active_object
        if self.selected_object is None or self.selected_object.type != "MESH":
            self.report({"WARNING"}, "No mesh object was selected.")

        self.material = self.selected_object.active_material

        self.settings = context.scene.easyLightMap

        # Check/Add UVs.
        check_uv_layers(self.selected_object)

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
        baked_slot.blend_type = "MULTIPLY"

        # Apply image to active UV layer.
        uv_layer = self.selected_object.data.uv_textures.active
        for uv in uv_layer.data:
            uv.image = baked_tex.image

        # Done!
        return {"FINISHED"}


class EasyLightMapBake(bpy.types.Operator):

    bl_idname = "object.easy_light_map_bake"
    bl_label = "Bake It!"
    bl_description = "Bake light map into new texture and add it into object material."

    settings = None
    selected_object = None
    material = None
    #original_color = None
    #textures_use = []

    @classmethod
    def poll(cls, context):
        return True

    # def invoke(self, context, event):
    #     return self.execute(context)

    def execute(self, context):
        self.selected_object = context.active_object
        if self.selected_object is None or self.selected_object.type != "MESH":
            self.report({"WARNING"}, "No mesh object was selected.")

        self.settings = context.scene.easyLightMap
        self.material = self.selected_object.active_material

        # Check UV layers.
        check_uv_layers(self.selected_object)

        # Add a new texture slot and a new image for baking.
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
        baked_slot.blend_type = "MULTIPLY"

        # Set UV layer image.
        uv_layer = self.selected_object.data.uv_textures.active
        for uv in uv_layer.data:
            uv.image = baked_tex.image

        if not self.settings.bake_diffuse:
            # Save diffuse color
            General.original_color = self.material.diffuse_color.copy()
            # Change it to pure white.
            self.material.diffuse_color = [1.0, 1.0, 1.0]

        # Check which texture to use.
        General.textures_use = self.get_used_textures()

        # Bake it.
        bpy.app.handlers.scene_update_post.append(scene_update)
        bpy.ops.object.bake_image("INVOKE_DEFAULT")
        General.is_baking_started = True

        # Done!
        return {"FINISHED"}

    def get_used_textures(self):
        """ UnCheck textures if bake_textures is false. """
        result = []
        for slot in self.material.texture_slots:
            if slot is not None and slot.use:
                result.append(slot.use)
                if not self.settings.bake_textures:
                    slot.use = False

        return result


class EasyLightMapPanel(bpy.types.Panel):

    bl_idname = "RENDER_PT_easy_light_map"
    bl_label = "Easy Light Map"
    bl_region_type = "WINDOW"
    bl_space_type = "PROPERTIES"
    bl_context = "render"

    @classmethod
    def poll(cls, context):
        # if context.scene.render.engine == "BLENDER_RENDER":
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
        row.prop(props, "bake_diffuse")
        row = layout.row(True)
        row.prop(props, "bake_textures")
        layout.separator()
        layout.operator(EasyLightMapPrepare.bl_idname, text="Only Prepare For Baking")
        layout.operator(EasyLightMapBake.bl_idname, text="Bake it!")



def check_uv_layers(selected_object):
    """ Object must have two uv sets. """
    if len(selected_object.data.uv_textures) == 0:
        add_uv_map("Diffuse", selected_object)
        add_uv_map("LightMap", selected_object)
    elif len(selected_object.data.uv_textures) == 1:
        add_uv_map("LightMap", selected_object)


def add_uv_map(name, selected_object):
    """ Add new UV Map to object and unwrap it. """
    uv = selected_object.data.uv_textures.new(name)
    uv.active = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(island_margin=0.05)
    # Have to pass object, because context.object is None in render panel.
    # (in unwrap function is_editmode = (context.object.mode == 'EDIT') will need it.)
    # bpy.ops.uv.lightmap_pack({
    #                          "object": selected_object,
    #                          "PREF_CONTEXT": "ALL_OBJECTS",
    #                          "PREF_PACK_IN_ONE": True,
    #                          "PREF_IMG_PX_SIZE": settings.image_w
    #                         })
    bpy.ops.object.mode_set(mode="OBJECT")
    uv.active = True

    return uv


@persistent
def scene_update(context):
    # Just when baking started texture.is_updated is true, after that it'll becomes false.
    if bpy.context.active_object:
        material = bpy.context.active_object.active_material
        name = "Baked_" + material.name

        if General.is_baking_started and not bpy.data.textures[name].is_updated:
            # Baking is finished, so revert back the material color and texture slots use check boxes.
            if General.original_color is not None:
                material.diffuse_color = General.original_color

            for index in range(len(General.textures_use)):
                if material.texture_slots[index] is not None:
                    material.texture_slots[index].use = General.textures_use.pop(0)

            # Remove handler
            bpy.app.handlers.scene_update_post.remove(scene_update)



def register():
    bpy.utils.register_class(EasyLightMapProperties)
    bpy.types.Scene.easyLightMap = bpy.props.PointerProperty(type=EasyLightMapProperties)
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)


if __name__ == "__main__":
    register()
