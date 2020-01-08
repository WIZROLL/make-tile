import os
from math import radians
from .. utils.registration import get_prefs
import bpy
from .. lib.turtle.scripts.openlock_floor_tri_base import draw_openlock_tri_floor_base
from .. lib.turtle.scripts.primitives import draw_tri_prism
from .. lib.utils.collections import add_object_to_collection
from .. lib.utils.utils import mode
from .. lib.utils.selection import select, activate, deselect_all, select_all, select_by_loc
from . create_displacement_mesh import create_displacement_object
from .. materials.materials import (
    assign_displacement_materials,
    assign_preview_materials)
from .. lib.utils.vertex_groups import tri_prism_to_vert_groups
from .. operators.trim_tile import (
    create_tri_floor_tile_trimmers,
    add_bool_modifier)


def create_triangular_floor(tile_empty):
    """Creates a triangular floor"""
    # hack to correct for parenting issues.
    # moves cursor to origin and creates objects
    # then moves base to cursor original location and resets cursor
    # TODO: get rid of hack and parent properly
    scene = bpy.context.scene
    cursor = scene.cursor
    cursor_orig_loc = cursor.location.copy()
    cursor.location = (0, 0, 0)
    tile_empty.location = (0, 0, 0)

    tile_props = bpy.context.collection.mt_tile_props
    tile_name = tile_props.tile_name

    # Get base and main part blueprints
    base_blueprint = tile_props.base_blueprint
    main_part_blueprint = tile_props.main_part_blueprint

    # store some tile props
    tile_props.leg_1_len = scene.mt_leg_1_len
    tile_props.leg_2_len = scene.mt_leg_2_len
    tile_props.angle = scene.mt_angle

    # We store a list of meshes here because we're going to add
    # trimmer modifiers to all of them later but we don't yet
    # know the full dimensions of our tile
    tile_meshes = []

    if base_blueprint == 'OPENLOCK':
        tile_props.base_size[2] = .2756
        tile_props.tile_size[2] = 0.374
        base, dimensions = create_openlock_base(tile_props)
        tile_meshes.append(base)

    if base_blueprint == 'PLAIN':
        tile_props.base_size[2] = scene.mt_base_z
        tile_props.tile_size[2] = scene.mt_tile_z
        base, dimensions = create_plain_base(tile_props)
        tile_meshes.append(base)

    if base_blueprint == 'NONE':
        tile_props.base_size = (0, 0, 0)
        base = bpy.data.objects.new(tile_props.tile_name + '.base', None)
        tile_props.tile_size[2] = scene.mt_tile_z
        add_object_to_collection(base, tile_props.tile_name)

    if main_part_blueprint == 'NONE':
        tile_props.tile_size = tile_props.base_size
    
    else:
        # slabs are the textured part of the tile
        preview_slab, displacement_slab, dimensions = create_slabs(tile_props, base)
        tile_meshes.extend([preview_slab, displacement_slab])

    trimmers = create_tri_floor_tile_trimmers(tile_props, dimensions, tile_empty)

    for obj in tile_meshes:
        for trimmer in trimmers:
            add_bool_modifier(obj, trimmer.name)
            trimmer.display_type = 'WIRE'
            trimmer.hide_viewport = True

    base.parent = tile_empty

    tile_empty.location = cursor_orig_loc
    cursor.location = cursor_orig_loc


def create_slabs(tile_props, base):
    turtle = bpy.context.scene.cursor
    t = bpy.ops.turtle

    t.add_turtle()
    t.add_vert()
    t.pd()
    floor, dimensions = draw_tri_prism(
        tile_props.leg_1_len,
        tile_props.leg_2_len,
        tile_props.angle,
        tile_props.tile_size[2] - tile_props.base_size[2])
    tri_prism_to_vert_groups(bpy.context.object, dimensions, tile_props.tile_size[2] - tile_props.base_size[2])
    t.select_all()
    t.up(d=tile_props.base_size[2], m=True)

    mode('OBJECT')
    obj = bpy.context.object

    preview_slab, displacement_slab = create_displacement_object(obj)

    preferences = get_prefs()

    primary_material = bpy.data.materials[bpy.context.scene.mt_tile_material_1]
    secondary_material = bpy.data.materials[preferences.secondary_material]

    image_size = bpy.context.scene.mt_tile_resolution

    assign_displacement_materials(displacement_slab, [image_size, image_size], primary_material, secondary_material)
    assign_preview_materials(preview_slab, primary_material, secondary_material, ['Top'])
    slabs = [preview_slab, displacement_slab]

    for slab in slabs:
        deselect_all()
        select(slab.name)
        bpy.ops.uv.smart_project()
        slab.parent = base
    displacement_slab.hide_viewport = True

    return preview_slab, displacement_slab, dimensions


def create_openlock_base(tile_props):
    base, dimensions = draw_openlock_tri_floor_base(
        tile_props.leg_1_len,
        tile_props.leg_2_len,
        tile_props.base_size[2],
        tile_props.angle)
    base.name = tile_props.tile_name + '.base'
    add_object_to_collection(base, tile_props.tile_name)
    base['geometry_type'] = 'BASE'

    clip_cutters = create_openlock_base_clip_cutters(base, dimensions, tile_props)

    for clip_cutter in clip_cutters:
        matrixcopy = clip_cutter.matrix_world.copy()
        clip_cutter.parent = base
        clip_cutter.matrix_world = matrixcopy
        clip_cutter.display_type = 'BOUNDS'
        clip_cutter.hide_viewport = True
        clip_cutter_bool = base.modifiers.new('Clip Cutter', 'BOOLEAN')
        clip_cutter_bool.operation = 'DIFFERENCE'
        clip_cutter_bool.object = clip_cutter
    return base, dimensions


def create_openlock_base_clip_cutters(base, dimensions, tile_props):

    if dimensions['a'] or dimensions['b'] or dimensions['c'] >= 2:
        mode('OBJECT')
        deselect_all()
        base_location = base.location.copy()
        preferences = get_prefs()
        booleans_path = os.path.join(preferences.assets_path, "meshes", "booleans", "openlock.blend")

        cutters = []
        with bpy.data.libraries.load(booleans_path) as (data_from, data_to):
            data_to.objects = ['openlock.wall.base.cutter.clip', 'openlock.wall.base.cutter.clip.cap.start', 'openlock.wall.base.cutter.clip.cap.end']

        for obj in data_to.objects:
            add_object_to_collection(obj, tile_props.tile_name)

        clip_cutter_1 = data_to.objects[0]
        cutter_start_cap = data_to.objects[1]
        cutter_end_cap = data_to.objects[2]

        cutter_start_cap.hide_viewport = True
        cutter_end_cap.hide_viewport = True

        array_mod = clip_cutter_1.modifiers.new('Array', 'ARRAY')
        array_mod.start_cap = cutter_start_cap
        array_mod.end_cap = cutter_end_cap
        array_mod.use_merge_vertices = True

        array_mod.fit_type = 'FIT_LENGTH'

        # for cutters the number of cutters and start and end location has to take into account
        # the angles of the triangle in order to prevent overlaps between cutters
        # and issues with booleans

        # cutter 1
        if dimensions['c'] >= 2:
            if dimensions['A'] >= 90:
                clip_cutter_1.location = (
                    dimensions['loc_A'][0] + 0.5,
                    dimensions['loc_A'][1] + 0.25,
                    dimensions['loc_A'][2])
                if dimensions['C'] >= 90:
                    array_mod.fit_length = dimensions['c'] - 1
                else:
                    array_mod.fit_length = dimensions['c'] - 1.5

            elif dimensions['A'] < 90:
                clip_cutter_1.location = (
                    dimensions['loc_A'][0] + 1,
                    dimensions['loc_A'][1] + 0.25,
                    dimensions['loc_A'][2])
                if dimensions['C'] >= 90:
                    array_mod.fit_length = dimensions['c'] - 1.5
                else:
                    array_mod.fit_length = dimensions['c'] - 2

            deselect_all()
            select(clip_cutter_1.name)
            bpy.ops.transform.rotate(
                value=(radians(dimensions['A'] - 90)),
                orient_axis='Z',
                orient_type='GLOBAL',
                center_override=dimensions['loc_A'])

            deselect_all()

            # cutter 2
            clip_cutter_2 = clip_cutter_1.copy()
            add_object_to_collection(clip_cutter_2, tile_props.tile_name)
            cutters.append(clip_cutter_1)
        else:
            clip_cutter_2 = clip_cutter_1

        if dimensions['b'] >= 2:
            array_mod = clip_cutter_2.modifiers['Array']

            if dimensions['B'] >= 90:
                clip_cutter_2.location = (
                    dimensions['loc_B'][0] + 0.25,
                    dimensions['loc_B'][1] - 0.5,
                    dimensions['loc_B'][2])
                if dimensions['A'] >= 90:
                    array_mod.fit_length = dimensions['b'] - 1
                else:
                    array_mod.fit_length = dimensions['b'] - 1.5

            elif dimensions['B'] < 90:
                clip_cutter_2.location = (
                    dimensions['loc_B'][0] + 0.25,
                    dimensions['loc_B'][1] - 1,
                    dimensions['loc_B'][2])
                if dimensions['A'] >= 90:
                    array_mod.fit_length = dimensions['b'] - 1.5
                else:
                    array_mod.fit_length = dimensions['b'] - 2

            clip_cutter_2.rotation_euler = (0, 0, radians(-90))
            cutters.append(clip_cutter_2)
            if dimensions['a'] >= 2:
                clip_cutter_3 = clip_cutter_2.copy()
                add_object_to_collection(clip_cutter_3, tile_props.tile_name)
            else:
                bpy.ops.object.make_single_user(type='ALL', object=True, obdata=True)
                return cutters
        else:
            clip_cutter_3 = clip_cutter_2

        # clip cutter 3
        if dimensions['a'] >= 2:
            clip_cutter_3.rotation_euler = (0, 0, 0)
            array_mod = clip_cutter_3.modifiers['Array']

            if dimensions['C'] >= 90:
                clip_cutter_3.location = (
                    dimensions['loc_C'][0] + 0.5,
                    dimensions['loc_C'][1] + 0.25,
                    dimensions['loc_C'][2])
                if dimensions['B'] >= 90:
                    array_mod.fit_length = dimensions['a'] - 1
                else:
                    array_mod.fit_length = dimensions['a'] - 1.5

            elif dimensions['C'] < 90:
                clip_cutter_3.location = (
                    dimensions['loc_C'][0] + 1,
                    dimensions['loc_C'][1] + 0.25,
                    dimensions['loc_C'][2])
                if dimensions['B'] >= 90:
                    array_mod.fit_length = dimensions['a'] - 1.5
                else:
                    array_mod.fit_length = dimensions['a'] - 2
            deselect_all()
            select(clip_cutter_3.name)

            bpy.ops.transform.rotate(
                value=(-radians(90 + dimensions['C'])),
                orient_axis='Z',
                orient_type='GLOBAL',
                center_override=dimensions['loc_C'])

            deselect_all()
            cutters.append(clip_cutter_3)
            bpy.ops.object.make_single_user(type='ALL', object=True, obdata=True)

        return cutters

    else:

        return None


def create_plain_base(tile_props):
    turtle = bpy.context.scene.cursor
    t = bpy.ops.turtle

    t.add_turtle()
    t.add_vert()
    t.pd()
    base, dimensions = draw_tri_prism(
        tile_props.leg_1_len,
        tile_props.leg_2_len,
        tile_props.angle,
        tile_props.base_size[2])
    t.pu()
    t.home()
    mode('OBJECT')
    return base, dimensions
