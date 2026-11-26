"""Blender 렌더: 센서 정육면체 단면 (Servier 피부 블록과 같은 시점·잘린 면).

구조 (세미나 S10–S11): 베이스 실리콘 1000 µm → EGaIn 스파이럴 DIW (선폭 400 µm, 피치 700 µm) → 브리지 → 커버 실리콘 500 µm → 범프 → 두 선 리드.
보이게 하려고 두께 ×4, 턴 수 6, 선 굵기를 과장한다 (그림에 "not to scale").
실행: "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P Paper/concept_fig/render_sensor_cube.py
→ Paper/concept_fig/assets/sensor_cube.png (배경 투명)
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent / "assets" / "sensor_cube.png"
TURNS, PITCH, R_W = 6, 1.25, 0.38            # 턴, 피치, 선 반지름 [mm, 과장]
A0, B0 = 10.0, 20.0                          # 바깥 반폭 (20 × 40 mm)
Z_BASE, Z_TOP = 4.0, 6.0                     # 베이스 윗면, 커버 윗면 (두께 ×4)
X_LIM, Y_CUT, Y_END = 14.0, -12.0, 25.0      # 블록: x ±14, 앞 잘린 면 y = −12
X_PEEL = 0.5                                 # 커버는 x > 0.5 만 (왼쪽은 벗겨 코일을 보임)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat_silicone(name, color, transm, rough=0.3, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.41
    b.inputs["Alpha"].default_value = alpha
    for key in ("Transmission Weight", "Transmission"):
        if key in b.inputs:
            b.inputs[key].default_value = transm
    return m


def mat_metal(name, color, rough=0.18):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = rough
    return m


def box(name, x0, x1, y0, y1, z0, z1, mat):
    bpy.ops.mesh.primitive_cube_add(location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.scale = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    return o


def tube(name, pts, r, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution = r, 6
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    o.select_set(False)
    return o


def clip(o, cutter):
    """블록 안쪽만 남김 (Boolean INTERSECT)."""
    m = o.modifiers.new("clip", "BOOLEAN")
    m.operation, m.object, m.solver = "INTERSECT", cutter, "EXACT"
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier="clip")


def spiral_pts():
    z = Z_BASE + R_W * 0.9
    pts = [(-A0 - 3.0, -B0, z)]
    for k in range(TURNS):
        a, b = A0 - k * PITCH, B0 - k * PITCH
        pts += [(-a, -b, z), (-a, b, z), (a, b, z), (a, -b, z), (-a + PITCH, -b, z)]
    return pts, (A0 - TURNS * PITCH, B0 - TURNS * PITCH, z)


def main():
    reset()
    sc = bpy.context.scene
    sil_base = mat_silicone("base", (0.50, 0.68, 0.90), 0.0, 0.5)
    sil_cover = mat_silicone("cover", (0.84, 0.91, 0.99), 0.0, 0.35)
    egain = mat_metal("EGaIn", (0.86, 0.87, 0.90), 0.22)
    lead = mat_metal("lead", (0.85, 0.62, 0.25), 0.3)

    box("base", -X_LIM, X_LIM, Y_CUT, Y_END, 0, Z_BASE, sil_base)
    cover = box("cover", X_PEEL, X_LIM, Y_CUT, Y_END, Z_BASE, Z_TOP, sil_cover)
    for bx in (7.5,):                                          # 범프 (커버 위)
        for by in (-5.0, 5.0, 15.0):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=2.6, location=(bx, by, Z_TOP - 1.2), segments=48, ring_count=24)
            sp = bpy.context.object
            m = cover.modifiers.new("bump", "BOOLEAN"); m.operation, m.object, m.solver = "UNION", sp, "EXACT"
            bpy.context.view_layer.objects.active = cover
            bpy.ops.object.modifier_apply(modifier="bump")
            bpy.data.objects.remove(sp)
    cutter = box("cutter", -X_LIM + 0.01, X_LIM - 0.01, Y_CUT + 0.01, Y_END - 0.01, -1, 10, sil_base)
    pts, (ai, bi, z) = spiral_pts()
    coil = tube("coil", pts, R_W, egain)
    clip(coil, cutter)
    zb = Z_TOP - 0.45                                          # 브리지: 안쪽 끝 → 권선 위 → 바깥
    br = tube("bridge", [(ai - 0.2, bi - 3.0, z), (ai, bi - 3.0, zb), (A0 + 2.0, bi - 3.0, zb), (A0 + 3.0, bi - 3.0, z),
                         (A0 + 3.0, Y_END + 6, z)], R_W * 0.9, egain)
    clip(br, cutter)
    tube("lead_in", [(A0 + 3.0, Y_END - 1, z), (A0 + 3.0, Y_END + 9, z), (A0 + 5.5, Y_END + 13, z - 0.5)], 0.32, lead)
    # 바깥 끝 리드: 블록 왼쪽 앞 → 뒤로 (잘린 면 밖은 보이지 않으므로 뒤쪽에서 나가게)
    out = tube("outer_trace", [(-A0 - 3.0, Y_CUT - 1, z), (-A0 - 3.0, Y_END + 6, z)], R_W * 0.9, egain)
    clip(out, cutter)
    tube("lead_out", [(-A0 - 3.0, Y_END - 1, z), (-A0 - 3.0, Y_END + 9, z), (-A0 - 5.5, Y_END + 13, z - 0.5)], 0.32, lead)
    bpy.data.objects.remove(cutter)
    for o in list(sc.objects):                                  # 불리언 n-gon 줄무늬 제거
        if o.type == "MESH":
            bpy.context.view_layer.objects.active = o
            o.select_set(True)
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
            o.select_set(False)

    # 카메라 · 빛 (피부 블록과 비슷한 앞-오른쪽-위 시점)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.location = (38, -62, 44)
    cam.data.type, cam.data.ortho_scale = "ORTHO", 50
    d = Vector((0, 6, 0.5)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    for loc, e in (((30, -40, 60), 3000), ((-40, -20, 40), 1200), ((0, 60, 50), 900)):
        L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA"))
        L.data.energy, L.data.size = e, 30
        L.location = loc
        L.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(L)
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8

    sc.render.engine = "CYCLES"
    sc.cycles.samples = 256
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.0
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1250
    sc.render.filepath = str(OUT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


main()
