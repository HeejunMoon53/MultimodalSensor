"""Blender 렌더: PneuNet 2지 소프트 그리퍼 + 바닥층 센서 (배경 투명).

손가락 형상 = Hardware/pneunet_gripper CAD (STEP → assets/cad/*.stl, build123d 로 변환).
손가락 로컬 좌표: X = 길이 (0 = 뿌리), Y = 폭, Z = 두께 (바닥층 −4..0 = 물체 쪽, 몸체 0..20).
SimpleDeform BEND 로 바닥층 쪽으로 굽힌다 (공기를 넣은 모습, 그림용). 센서 = 바닥층 물체 쪽 면의 패드 + 스파이럴.
실행: "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P Paper/concept_fig/render_gripper.py
→ Paper/concept_fig/assets/gripper.png
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
CAD = HERE / "assets" / "cad"
OUT = HERE / "assets" / "gripper.png"
GAP = 48.0          # 손가락 바닥층 사이 반간격 [mm]
BEND = 50.0         # 굽힘 각 [°]


def mat(name, color, metal=0.0, rough=0.4, sss=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if sss and "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = sss
    return m


def stl(name, m):
    bpy.ops.wm.stl_import(filepath=str(CAD / f"{name}.stl"))
    o = bpy.context.selected_objects[0]
    o.data.materials.append(m)
    return o


def box(x0, x1, y0, y1, z0, z1, m):
    bpy.ops.mesh.primitive_cube_add(location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object
    o.scale = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    bpy.ops.object.transform_apply(location=True, scale=True)   # 원점 = 세계 원점 (나중 배치가 덮어쓰므로)
    o.data.materials.append(m)
    return o


def tube(pts, r, m):
    cu = bpy.data.curves.new("t", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", r, 4
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    o = bpy.data.objects.new("t", cu)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(m)
    return o


def to_mesh(o):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return o


def densify(o, voxel=None, cuts=0):
    """굽힘 전에 길이 방향으로 잘게: 실리콘은 Remesh, 얇은 선은 Subdivide."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    if voxel:
        r = o.modifiers.new("rm", "REMESH"); r.mode, r.voxel_size = "VOXEL", voxel
        bpy.ops.object.modifier_apply(modifier="rm")
    if cuts:
        bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.subdivide(number_cuts=cuts); bpy.ops.object.mode_set(mode="OBJECT")


def spiral(x0, x1, y0, y1, z, turns, pitch):
    pts = [(x0 - 3, y0, z)]
    a0, a1, b0, b1 = x0, x1, y0, y1
    for _ in range(turns):
        pts += [(a0, b0, z), (a1, b0, z), (a1, b1, z), (a0, b1, z), (a0, b0 + pitch, z)]
        a0, a1, b0, b1 = a0 + pitch, a1 - pitch, b0 + pitch, b1 - pitch
    return pts


def finger(mats, sign):
    """한 손가락 (로컬) → 굽힘 → 세계 배치. sign = +1 (x > 0 쪽) / −1."""
    parts = [stl("finger_body_silicone", mats["body"]), stl("finger_base_silicone", mats["base"])]
    for o in parts:
        densify(o, voxel=0.9)
    pad = box(35, 97, -12, 12, -4.7, -4.0, mats["sensor"])                    # 센서 패드 (바닥층 물체 쪽)
    densify(pad, cuts=30)
    coil = to_mesh(tube(spiral(40, 92, -9, 9, -4.95, 5, 1.6), 0.3, mats["egain"]))
    densify(coil, cuts=12)
    lead = to_mesh(tube([(37, -9, -4.95), (2, -9, -4.95), (-8, -9, -4.95)], 0.35, mats["lead"]))
    densify(lead, cuts=20)
    parts += [pad, coil, lead]
    # 굽힘 각은 객체 길이 범위로 나뉘므로, 부품을 한 메시로 합쳐 같은 곡률로 굽힌다 (재질은 면마다 유지)
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    o = parts[0]
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.join()
    pivot = bpy.data.objects.new("pivot", None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = (0, 0, -4.7)
    pivot.rotation_euler = (math.radians(90), 0, 0)                            # 굽힘 축 = 로컬 Y
    d = o.modifiers.new("bend", "SIMPLE_DEFORM")
    d.deform_method, d.angle, d.origin, d.deform_axis = "BEND", math.radians(-BEND), pivot, "Z"
    bpy.ops.object.modifier_apply(modifier="bend")
    # 로컬 → 세계: X → −Z (매달림), Z → +x·sign (등은 바깥, 바닥층은 가운데를 봄)
    o.rotation_euler = (0, math.radians(90), 0 if sign > 0 else math.radians(180))
    o.location = (sign * (GAP + 4.0), 0, 0)
    bpy.data.objects.remove(pivot)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    mats = dict(body=mat("body", (0.93, 0.93, 0.91), rough=0.45, sss=0.15),
                base=mat("base", (0.86, 0.87, 0.86), rough=0.5),
                sensor=mat("sensor", (0.50, 0.68, 0.90), rough=0.45),
                egain=mat("egain", (0.86, 0.87, 0.90), metal=1.0, rough=0.22),
                lead=mat("lead", (0.85, 0.62, 0.25), metal=1.0, rough=0.3),
                palm=mat("palm", (0.18, 0.19, 0.21), rough=0.5),
                hose=mat("hose", (0.20, 0.45, 0.80), rough=0.35))
    finger(mats, +1); finger(mats, -1)
    box(-74, 74, -24, 24, 0, 14, mats["palm"])                                 # 손바닥
    for sx in (+1, -1):                                                        # 공압 튜브
        tube([(sx * 55, 0, 14), (sx * 55, 0, 40), (sx * 80, 0, 70)], 2.2, mats["hose"])
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.location = (-150, -230, -10)
    cam.data.lens = 36
    cam.rotation_euler = (Vector((0, 0, -55)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    for loc, e in (((150, -200, 200), 1.2e6), ((-250, -100, 50), 5e5), ((0, 250, 150), 4e5)):
        L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA"))
        L.data.energy, L.data.size = e, 150
        L.location = loc
        L.rotation_euler = (Vector((0, 0, -50)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(L)
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.4
    sc.render.engine = "CYCLES"
    sc.cycles.samples, sc.cycles.use_denoising = 160, True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 1200, 1500
    sc.render.filepath = str(OUT)
    bpy.ops.render.render(write_still=True)


main()
