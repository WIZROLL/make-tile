import os
import bpy
from math import radians
from .. lib.turtle.scripts.curved_floor import draw_neg_curved_slab, draw_pos_curved_slab, draw_openlock_pos_curved_base
from .. lib.utils.vertex_groups import curved_floor_to_vert_groups
from .. utils.registration import get_prefs
from .. materials.materials import (
    assign_displacement_materials,
    assign_preview_materials)
from . create_displacement_mesh import create_displacement_object
from .. lib.utils.selection import select, activate, deselect_all, select_all, select_by_loc
from .. lib.utils.utils import mode
from .. lib.utils.collections import add_object_to_collection
from .create_corner_wall import calculate_corner_wall_triangles, move_cursor_to_wall_start, draw_corner_outline
from ..operators.trim_tile import (
    create_curved_floor_trimmers,
    add_bool_modifier)


def create_curved_floor(tile_empty):
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

    tile_props.base_radius = scene.mt_base_radius
    tile_props.segments = scene.mt_segments
    tile_props.angle = scene.mt_angle
    tile_props.base_size[2] = scene.mt_base_z
    tile_props.tile_size[2] = scene.mt_tile_z
    tile_props.curve_type = scene.mt_curve_type

    cursor = bpy.context.scene.cursor
    cursor_orig_loc = cursor.location.copy()
    cursor.location = (0, 0, 0)
    tile_empty.location = (0, 0, 0)

    tile_meshes = []

    if base_blueprint == 'OPENLOCK':
        tile_props.base_size[2] = 0.2756
        tile_props.tile_size[2] = 0.374
        base = create_openlock_base(tile_props)
        tile_meshes.append(base)
    if base_blueprint == 'PLAIN':
        base = create_plain_base(tile_props)
        tile_meshes.append(base)

    if base_blueprint == 'NONE':
        tile_properties['base_size'] = (0, 0, 0)
        base = bpy.data.objects.new(tile_props.tile_name + '.base', None)
        add_object_to_collection(base, tile_props.tile_name)

    if main_part_blueprint != 'NONE':
        preview_slab, displacement_slab = create_slabs(tile_props, base)
        tile_meshes.extend([preview_slab, displacement_slab])
        displacement_slab.hide_viewport = True

    trimmers = create_curved_floor_trimmers(tile_props, tile_empty)

    for obj in tile_meshes:
        for trimmer in trimmers:
            add_bool_modifier(obj, trimmer.name)
            trimmer.display_type = 'WIRE'
            #trimmer.hide_viewport = True

    base.parent = tile_empty
    tile_empty.location = cursor_orig_loc
    cursor.location = cursor_orig_loc


def create_plain_base(tile_props):
    cursor = bpy.context.scene.cursor
    cursor_orig_loc = cursor.location.copy()

    radius = tile_props.base_radius
    segments = tile_props.segments
    angle = tile_props.angle
    height = tile_props.base_size[2]
    curve_type = tile_props.curve_type

    if curve_type == 'POS':
        draw_pos_curved_slab(radius, segments, angle, height)
    else:
        draw_neg_curved_slab(radius, segments, angle, height)
    base = bpy.context.object
    base['geometry_type'] = 'BASE'
    cursor.location = cursor_orig_loc
    select(base.name)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    deselect_all()
    return base


def create_openlock_base(tile_props):
    cursor = bpy.context.scene.cursor
    cursor_orig_loc = cursor.location.copy()

    length = tile_props.base_radius
    segments = tile_props.segments
    angle = tile_props.angle
    height = tile_props.base_size[2]
    curve_type = tile_props.curve_type

    if curve_type == 'POS':
        draw_openlock_pos_curved_base(length, segments, angle, height)
        base = bpy.context.object

        base['geometry_type'] = 'BASE'
        cursor.location = cursor_orig_loc
        select(base.name)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        deselect_all()

    else:
        draw_neg_curved_slab(length, segments, angle, height)
        base = bpy.context.object
        base['geometry_type'] = 'BASE'
        cursor.location = cursor_orig_loc
        select(base.name)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        deselect_all()

        if length >= 3:
            cutter = create_openlock_neg_curve_base_cutters(tile_props)
            cutter.parent = base
            cutter.display_type = 'BOUNDS'
            cutter.hide_viewport = True
            cutter_bool = base.modifiers.new('Slot Cutter', 'BOOLEAN')
            cutter_bool.operation = 'DIFFERENCE'
            cutter_bool.object = cutter

    cutters = create_openlock_base_clip_cutters(base, tile_props)

    for clip_cutter in cutters:
        matrixcopy = clip_cutter.matrix_world.copy()
        clip_cutter.parent = base
        clip_cutter.matrix_world = matrixcopy
        clip_cutter.display_type = 'BOUNDS'
        clip_cutter.hide_viewport = True
        clip_cutter_bool = base.modifiers.new('Clip Cutter', 'BOOLEAN')
        clip_cutter_bool.operation = 'DIFFERENCE'
        clip_cutter_bool.object = clip_cutter

    return base


def create_openlock_neg_curve_base_cutters(tile_props):
    cursor = bpy.context.scene.cursor
    cursor_orig_loc = cursor.location.copy()

    length = tile_props.base_radius / 2
    segments = tile_props.segments
    angle = tile_props.angle
    height = tile_props.base_size[2]
    curve_type = tile_props.curve_type
    face_dist = 0.233
    slot_width = 0.197
    slot_height = 0.25
    end_dist = 0.236  # distance of slot from base end

    cutter_triangles_1 = calculate_corner_wall_triangles(
        length,
        length,
        face_dist,
        angle)

    # reuse method we use to work out where to start our wall
    move_cursor_to_wall_start(
        cutter_triangles_1,
        angle,
        face_dist,
        -0.01)

    cutter_x_leg = cutter_triangles_1['b_adj'] - end_dist
    cutter_y_leg = cutter_triangles_1['d_adj'] - end_dist

    # work out dimensions of cutter
    cutter_triangles_2 = calculate_corner_wall_triangles(
        cutter_x_leg,
        cutter_y_leg,
        slot_width,
        angle
    )

    draw_corner_outline(
        cutter_triangles_2,
        angle,
        slot_width
    )

    # fill face and extrude cutter
    turtle = bpy.context.scene.cursor
    t = bpy.ops.turtle
    bpy.ops.mesh.edge_face_add()
    t.pd()
    t.up(d=slot_height)
    t.select_all()
    bpy.ops.mesh.normals_make_consistent()
    bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
    t.pu()
    t.deselect_all()
    t.home()

    mode('OBJECT')
    cutter = bpy.context.object
    cutter.name = tile_props.tile_name + '.base.cutter'

    return cutter


def create_openlock_base_clip_cutters(base, tile_props):

    mode('OBJECT')
    deselect_all

    cursor = bpy.context.scene.cursor
    cursor_orig_loc = cursor.location.copy()

    radius = tile_props.base_radius
    segments = tile_props.segments
    angle = tile_props.angle
    height = tile_props.base_size[2]
    curve_type = tile_props.curve_type
    cutters = []
    if curve_type == 'NEG':
        radius = radius / 2

    if radius >= 1:
        preferences = get_prefs()
        booleans_path = os.path.join(preferences.assets_path, "meshes", "booleans", "openlock.blend")

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

        if angle >= 90:
            clip_cutter_1.location = (
                cursor_orig_loc[0] + 0.5,
                cursor_orig_loc[1] + 0.25,
                cursor_orig_loc[2]
            )
            array_mod.fit_length = radius - 1
        else:
            clip_cutter_1.location = (
                cursor_orig_loc[0] + 1,
                cursor_orig_loc[1] + 0.25,
                cursor_orig_loc[2]
            )
            array_mod.fit_length = radius - 1.5

        deselect_all()
        select(clip_cutter_1.name)

        bpy.ops.transform.rotate(
            value=(radians(angle - 90)),
            orient_axis='Z',
            orient_type='GLOBAL',
            center_override=cursor_orig_loc)

        cutters.append(clip_cutter_1)
        # cutter 2
        clip_cutter_2 = clip_cutter_1.copy()
        add_object_to_collection(clip_cutter_2, tile_props.tile_name)

        array_mod = clip_cutter_2.modifiers['Array']

        if angle >= 90:
            clip_cutter_2.location = (
                cursor_orig_loc[0] + 0.25,
                cursor_orig_loc[1] + radius - 0.5,
                cursor_orig_loc[2]
            )
            array_mod.fit_length = radius - 1
        else:
            clip_cutter_2.location = (
                cursor_orig_loc[0] + 0.25,
                cursor_orig_loc[1] + radius - 0.5,
                cursor_orig_loc[2]
            )
            array_mod.fit_length = radius - 1.5

        clip_cutter_2.rotation_euler = (0, 0, radians(-90))
        cutters.append(clip_cutter_2)

        deselect_all()

    if tile_props.curve_type == 'POS':
        with bpy.data.libraries.load(booleans_path) as (data_from, data_to):
            data_to.objects = ['openlock.wall.base.cutter.clip_single']
        clip_cutter_3 = data_to.objects[0]
        add_object_to_collection(clip_cutter_3, tile_props.tile_name)

        deselect_all()
        select(clip_cutter_3.name)

        clip_cutter_3.rotation_euler = (0, 0, radians(180))
        clip_cutter_3.location[1] = cursor_orig_loc[1] + radius - 0.25
        bpy.ops.transform.rotate(
            value=(radians(angle / 2)),
            orient_axis='Z',
            orient_type='GLOBAL',
            center_override=cursor_orig_loc)

        cutters.append(clip_cutter_3)

    return cutters


def create_slabs(tile_props, base):
    cursor = bpy.context.scene.cursor
    cursor_orig_loc = cursor.location.copy()

    radius = tile_props.base_radius
    segments = tile_props.segments
    angle = tile_props.angle
    height = tile_props.tile_size[2] - base.dimensions[2]
    curve_type = tile_props.curve_type

    cursor.location[2] = cursor.location[2] + base.dimensions[2]

    if curve_type == 'POS':
        draw_pos_curved_slab(radius, segments, angle, height)
    else:
        draw_neg_curved_slab(radius, segments, angle, height)

    preview_slab = bpy.context.object
    preview_slab, displacement_slab = create_displacement_object(preview_slab)

    preferences = get_prefs()

    primary_material = bpy.data.materials[bpy.context.scene.mt_tile_material_1]
    secondary_material = bpy.data.materials[preferences.secondary_material]

    image_size = bpy.context.scene.mt_tile_resolution
    deselect_all()
    curved_floor_to_vert_groups(preview_slab, height, radius)

    assign_displacement_materials(
        displacement_slab,
        [image_size, image_size],
        primary_material,
        secondary_material)
    assign_preview_materials(
        preview_slab,
        primary_material,
        secondary_material,
        ['Top'])

    slabs = [preview_slab, displacement_slab]

    cursor.location = cursor_orig_loc

    for slab in slabs:
        deselect_all()
        select(slab.name)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        bpy.ops.uv.smart_project()
        slab.parent = base

    return preview_slab, displacement_slab