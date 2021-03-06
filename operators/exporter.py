import os
from random import random
import bpy
from .. lib.utils.selection import select, deselect_all
from .. utils.registration import get_prefs
from .. enums.enums import units
from .voxeliser import voxelise
from .. lib.utils.collections import get_objects_owning_collections
from . bakedisplacement import (
    set_cycles_to_bake_mode,
    reset_renderer_from_bake,
    bake_displacement_map)
from . return_to_preview import reset_displacement_modifiers


class MT_OT_Export_Tile_Variants(bpy.types.Operator):
    bl_idname = "scene.mt_export_multiple_tile_variants"
    bl_label = "Export multiple tile variants"
    bl_options = {'REGISTER'}

    def execute(self, context):
        objects = bpy.data.objects

        selected_objects = context.selected_objects.copy()
        visible_objects = []

        for obj in bpy.data.objects:
            obj.select_set(False)

        tile_collections = set()

        # set up exporter options
        blend_units = bpy.context.scene.mt_units
        export_path = context.scene.mt_export_path

        if blend_units == 'CM':
            unit_multiplier = 10
        if blend_units == 'INCHES':
            unit_multiplier = 25.4

        if not os.path.exists(export_path):
            os.mkdir(export_path)

        for obj in selected_objects:
            obj_collections = get_objects_owning_collections(obj.name)

            for collection in obj_collections:
                tile_collections.add(collection)

        orig_settings = set_cycles_to_bake_mode()

        for collection in tile_collections:
            preview_obs = set()

            for obj in collection.objects:
                if obj.mt_object_props.geometry_type == 'PREVIEW':
                    preview_obs.add(obj)

                if obj.visible_get() is True:
                    visible_objects.append(obj)

            i = 0
            while i < context.scene.mt_num_variants:
                disp_obs = []

                for obj in preview_obs:
                    obj.hide_viewport = False
                    disp_obj = obj.mt_object_props.linked_object

                    for item in obj.material_slots.items():
                        if item[0]:
                            material = bpy.data.materials[item[0]]
                            tree = material.node_tree
                        if 'Seed' in tree.nodes:
                            seed_node = tree.nodes['Seed']
                            rand_seed = random()
                            seed_node.outputs[0].default_value = rand_seed * 1000
                    if disp_obj not in visible_objects:
                        disp_obj_is_visible = False
                        disp_obj.hide_viewport = False
                        disp_obj.hide_set(False)
                    else:
                        disp_obj_is_visible = True


                    # Bake displacement map and apply to displacement obj
                    disp_image, disp_obj = bake_displacement_map(obj, disp_obj)
                    disp_texture = disp_obj['disp_texture']
                    disp_texture.image = disp_image
                    disp_mod = disp_obj.modifiers[disp_obj['disp_mod_name']]
                    disp_mod.texture = disp_texture
                    disp_mod.mid_level = 0
                    disp_mod.strength = collection.mt_tile_props.displacement_strength
                    subsurf_mod = disp_obj.modifiers[disp_obj['subsurf_mod_name']]
                    subsurf_mod.levels = bpy.context.scene.mt_scene_props.mt_subdivisions
                    disp_obs.append(disp_obj)

                disp_obj_copies = []

                depsgraph = context.evaluated_depsgraph_get()

                # create copy of each displacement object and apply modifiers
                for obj in disp_obs:
                    object_eval = obj.evaluated_get(depsgraph)
                    mesh_from_eval = bpy.data.meshes.new_from_object(object_eval)
                    dup_obj = bpy.data.objects.new("dupe", mesh_from_eval)
                    dup_obj.mt_object_props.geometry_type = 'DISPLACEMENT'

                    # set dupe objects locrotscale and parent to original object
                    dup_obj.location = obj.location
                    dup_obj.rotation_euler = obj.rotation_euler
                    dup_obj.scale = obj.scale
                    dup_obj.parent = obj.parent
                    collection.objects.link(dup_obj)
                    disp_obj_copies.append(dup_obj)

                    # hide original, resetting disp modifiers if disp_object was not originally visible
                    if disp_obj_is_visible is False:
                        reset_displacement_modifiers(obj)
                    obj.hide_viewport = True

                # Voxelise if necessary
                if context.scene.mt_voxelise_on_export is True:
                    for obj in disp_obj_copies:
                        obj.data.remesh_voxel_size = bpy.context.scene.mt_voxel_quality
                        obj.data.remesh_voxel_adaptivity = bpy.context.scene.mt_voxel_adaptivity
                        ctx = {
                            'object': obj,
                            'active_object': obj,
                            'selected_objects': [obj]
                        }

                        bpy.ops.object.voxel_remesh(ctx)
                        obj.mt_object_props.geometry_type = 'VOXELISED'

                # construct filepath
                file_path = os.path.join(
                    context.scene.mt_export_path,
                    collection.name + '.' + str(random()) + '.stl')

                export_objects = []
                export_objects.extend(disp_obj_copies)

                for obj in collection.all_objects:
                    if obj.mt_object_props.geometry_type not in ('PREVIEW', 'DISPLACEMENT') and \
                            obj not in disp_obj_copies and \
                            obj.visible_get() is True:

                        export_objects.append(obj)

                ctx = {
                    'selected_objects': export_objects,
                    'object': export_objects[0],
                    'active_object': export_objects[0]
                }

                # export our tile
                bpy.ops.export_mesh.stl(
                    ctx,
                    filepath=file_path,
                    check_existing=True,
                    filter_glob="*.stl",
                    use_selection=True,
                    global_scale=unit_multiplier,
                    use_mesh_modifiers=True)

                # Delete copies
                for obj in disp_obj_copies:
                    # obj.select_set(False)
                    objects.remove(obj, do_unlink=True)

                # unhide preview objects
                for obj in preview_obs:
                    obj.hide_viewport = False
                    obj.hide_set(False)

                i += 1

            for obj in preview_obs:
                obj.select_set(False)
                obj.hide_viewport = True

        reset_renderer_from_bake(orig_settings)

        # select original objects
        for obj in selected_objects:
            obj.select_set(True)

        # unhide original visible objects
        for obj in visible_objects:
            obj.hide_viewport = False
            obj.hide_set(False)

        return {'FINISHED'}


class MT_OT_Export_Tile(bpy.types.Operator):
    '''Exports visible contents of current tile as an .stl.'''

    bl_idname = "scene.mt_export_tile"
    bl_label = "Export tile"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.mode == 'OBJECT' and obj.mt_object_props.is_mt_object is True

    def execute(self, context):
        if context.scene.mt_randomise_on_export is True:
            bpy.ops.scene.mt_export_multiple_tile_variants()
            return {'PASS_THROUGH'}

        objects = bpy.data.objects
        selected_objects = context.selected_objects.copy()
        obj = context.active_object
        obj_props = obj.mt_object_props

        # set up exporter options
        blend_units = bpy.context.scene.mt_units
        export_path = context.scene.mt_export_path

        if blend_units == 'CM':
            unit_multiplier = 10

        if blend_units == 'INCHES':
            unit_multiplier = 25.4

        if not os.path.exists(export_path):
            os.mkdir(export_path)

        # check if active object is a MT object, if so we export everything
        # in the collection corresponding to the object's mt_object_props.tile_name
        if obj_props.is_mt_object is True:
            tile_name = obj_props.tile_name
            tile_collection = bpy.data.collections[tile_name]

            # save list of visible objects in tile collection
            visible_objects = []
            for obj in tile_collection.all_objects:
                if obj.type == 'MESH':
                    if obj.visible_get() is True:
                        visible_objects.append(obj)

            displacement_copies = []
            depsgraph = context.evaluated_depsgraph_get()

            # create copy of any displacement objects and flatten
            for obj in visible_objects:
                if obj.mt_object_props.geometry_type == 'DISPLACEMENT':
                    object_eval = obj.evaluated_get(depsgraph)
                    mesh_from_eval = bpy.data.meshes.new_from_object(object_eval)

                    dup_obj = bpy.data.objects.new("dupe", mesh_from_eval)
                    dup_obj.mt_object_props.geometry_type = 'DISPLACEMENT'
                    dup_obj.location = obj.location
                    dup_obj.rotation_euler = obj.rotation_euler
                    dup_obj.scale = obj.scale
                    dup_obj.parent = obj.parent
                    tile_collection.objects.link(dup_obj)
                    displacement_copies.append(dup_obj)
                    obj.hide_viewport = True

            # join displacement copies together
            if len(displacement_copies) > 1:
                ctx = {
                    'object': displacement_copies[0],
                    'active_object': displacement_copies[0],
                    'selected_objects': displacement_copies,
                    'selected_editable_objects': displacement_copies
                }
                bpy.ops.object.join(ctx)

            # voxelise displacement copies if neccessary
            for obj in displacement_copies:
                if context.scene.mt_voxelise_on_export is True:
                    voxelise(obj)

            file_path = os.path.join(
                context.scene.mt_export_path,
                tile_collection.name + '.' + str(random()) + '.stl')

            # create array of objects to export
            export_objects = []

            for obj in displacement_copies:
                export_objects.append(obj)

            for obj in visible_objects:
                if obj.mt_object_props.geometry_type != 'DISPLACEMENT':
                    export_objects.append(obj)

            ctx = {
                'selected_objects': export_objects,
                'active_object': export_objects[0],
                'object': export_objects[0]
            }

            # export our object
            bpy.ops.export_mesh.stl(
                ctx,
                filepath=file_path,
                check_existing=True,
                filter_glob="*.stl",
                use_selection=True,
                global_scale=unit_multiplier,
                use_mesh_modifiers=True)

            for obj in displacement_copies:
                objects.remove(objects[obj.name], do_unlink=True)

            for obj in visible_objects:
                obj.hide_viewport = False

            for obj in selected_objects:
                obj.select_set(True)

        # clean up orphaned meshes
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

        return {'FINISHED'}


def register():
    preferences = get_prefs()

    bpy.types.Scene.mt_export_path = bpy.props.StringProperty(
        name="Export Path",
        description="Path to export tiles to",
        subtype="DIR_PATH",
        default=preferences.default_export_path,
    )

    bpy.types.Scene.mt_units = bpy.props.EnumProperty(
        name="Units",
        items=units,
        description="Export units",
        default=preferences.default_units
    )

    bpy.types.Scene.mt_voxelise_on_export = bpy.props.BoolProperty(
        name="Voxelise",
        default=False
    )

    bpy.types.Scene.mt_randomise_on_export = bpy.props.BoolProperty(
        name="Randomise",
        description="Create random variant on export?",
        default=True
    )

    bpy.types.Scene.mt_num_variants = bpy.props.IntProperty(
        name="Variants",
        description="Number of variants of tile to export",
        default=1
    )

def unregister():
    del bpy.types.Scene.mt_voxelise_on_export
    del bpy.types.Scene.mt_units
    del bpy.types.Scene.mt_export_path
