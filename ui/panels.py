import os
import bpy


class MT_PT_Panel(bpy.types.Panel):
    bl_idname = "MT_PT_Panel"
    bl_label = "Make Tiles"
    bl_category = "Make-Tile"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):

        scene = context.scene
        layout = self.layout
        layout.operator('scene.make_tile', text="Make Tile")
        layout.prop(scene, 'mt_tile_blueprint')

        if scene.mt_tile_blueprint == 'OPENLOCK':
            self.draw_openlock_panel(context)

        if scene.mt_tile_blueprint == 'CUSTOM':
            layout.row()
            layout.prop(scene, 'mt_base_system')
            layout.prop(scene, 'mt_tile_main_system')

            if scene.mt_base_system or scene.mt_tile_main_system == 'PLAIN':
                layout.prop(scene, 'mt_tile_units')

            layout.prop(scene, 'mt_tile_type')
            '''
            TODO: Find out way of getting around not allowed message
            if scene.mt_tile_type == 'STRAIGHT_WALL':
                scene.mt_tile_x = 2
                scene.mt_tile_y = 0.5
                scene.mt_tile_z = 2
            if scene.mt_tile_type == 'RECTANGULAR_FLOOR':
                scene.mt_tile_x = 2
                scene.mt_tile_y = 2
                scene.mt_tile_z = 0.3
            '''
            if scene.mt_tile_type == 'STRAIGHT_WALL' or 'RECTANGULAR_FLOOR':
                layout.row()
                layout.prop(scene, 'mt_tile_x')
                layout.prop(scene, 'mt_tile_y')
                layout.prop(scene, 'mt_tile_z')

        layout.prop(scene, 'mt_tile_material')

        if bpy.context.object is not None:
            if bpy.context.object['geometry_type'] == 'PREVIEW':
                layout.operator('scene.bake_displacement', text='Make 3D')
            if bpy.context.object['geometry_type'] == 'DISPLACEMENT':
                layout.operator('scene.return_to_preview', text='Return to Preview')

    def draw_openlock_panel(self, context):
        scene = context.scene
        layout = self.layout

        scene.mt_tile_main_system == 'OPENLOCK'
        scene.mt_base_system == 'OPENLOCK'
        scene.mt_tile_units == 'IMPERIAL'

        layout.prop(scene, 'mt_tile_type')

        if scene.mt_tile_type == 'STRAIGHT_WALL':
            layout.row()
            layout.prop(scene, 'mt_tile_x')
            layout.prop(scene, 'mt_tile_z')

        elif scene.mt_tile_type == 'RECTANGULAR_FLOOR':
            layout.row()
            layout.prop(scene, 'mt_tile_x')
            layout.prop(scene, 'mt_tile_y')