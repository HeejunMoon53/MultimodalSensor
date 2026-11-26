"""Blender 렌더: PneuNet 2지 소프트 그리퍼 + 바닥층 센서 (배경 투명).

손가락 형상 = Hardware/pneunet_gripper CAD (STEP → assets/cad/*.stl, build123d 로 변환).
손가락 로컬 좌표: X = 길이 (0 = 뿌리), Y = 폭, Z = 두께 (바닥층 −4..0 = 물체 쪽, 몸체 0..20).
SimpleDeform BEND 로 바닥층 쪽으로 굽힌다 (공기를 넣은 모습, 그림용). 센서 = 바닥층 물체 쪽 면의 패드 + 스파이럴.
실행: "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P Paper/concept_fig/render_gripper.py -- [장면 ...] (all = 전부)
장면 (VARIANTS): gripper (기본, 물체 없음) · grip_egg (달걀 파지) · grip_touch (금속 봉이 두 패드에 닿음)
                 · grip_near (가는 금속 봉이 손가락 사이, 비접촉) · grip_human (손목이 두 패드에 닿음)
                 · 시나리오 s_* · a_* (망치 넘겨받기) · b_* (팔을 잘못 잡음) → assets/scenario/
→ Paper/concept_fig/assets/<장면>.png
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
CAD = HERE / "assets" / "cad"
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


def finger(mats, sign, bend=BEND):
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
    d.deform_method, d.angle, d.origin, d.deform_axis = "BEND", math.radians(-bend), pivot, "Z"
    bpy.ops.object.modifier_apply(modifier="bend")
    # 로컬 → 세계: X → −Z (매달림), Z → +x·sign (등은 바깥, 바닥층은 가운데를 봄)
    o.rotation_euler = (0, math.radians(90), 0 if sign > 0 else math.radians(180))
    o.location = (sign * (GAP + 4.0), 0, 0)
    bpy.data.objects.remove(pivot)


# 장면: 굽힘 각 [°], 물체 목록, 카메라. 패드 면 x ≈ ±47 (펼침).
#   물체: ("egg", z, r) · ("rod", z, r) 축 y · ("wrist", z, r) 축 y, 앞에 주먹 · ("cyl", z_bottom, r, h) 세운 금속 원기둥 · ("table", z_top)
#   카메라: pose (기본 3/4) · side (봉 · 손목, 축이 비스듬히) · scn (시나리오: 더 넓게, 아래까지)
CYL = lambda zb: ("cyl", zb, 30.0, 85.0)
WRIST = ("wrist", -72.0, 32.0)
ROD = ("cyl", -165.0, 13.0, 125.0)                        # 가는 금속 봉 (세움)
BLOCK = ("block", -100.0, 30.0, 26.0, 40.0)                # 나무 블록: 중심 z, 반폭 x · y · z
WRIST_H = ("wrist", -72.0, 32.0, True)                   # 주먹에 망치 손잡이 (B: 망치를 든 팔을 잘못 잡음)
HAM = lambda hc, hand=True: ("hammer", hc, hand)           # 망치: 강철 머리 중심 z (축 y), 손잡이는 아래로, hand = 손잡이를 쥔 손
VARIANTS = {
    "gripper": (BEND, [], "pose"), "grip_egg": (40.0, [("egg", -82.0, 22.0)], "pose"),
    "grip_touch": (8.0, [("rod", -70.0, 45.5)], "side"), "grip_near": (8.0, [("rod", -70.0, 28.0)], "side"),
    "grip_human": (8.0, [("wrist", -70.0, 45.5)], "side"),
    # 시나리오 (build_scenario_fig.py): A = 사람이 든 망치를 넘겨받음, B = 실수로 팔을 잡음
    "s_detect": (2.0, [HAM(-190.0)], "scn_lo"),
    "s_obj_metal": (None, [HAM(-120.0, False)], "scn"), "s_obj_hand": (None, [WRIST], "scn"),
    "a_approach": (6.0, [HAM(-150.0)], "scn_lo"),
    "a_contact": (22.0, [HAM(-88.0)], "scn"),
    "a_grasp": (30.0, [HAM(-88.0)], "scn"),
    "a_handover": (30.0, [HAM(-88.0, False)], "scn"),
    # 물체 식별 (2번째 시나리오): 도체/유전체 × 큼/작음. 닿을 때까지 굽힘 = 고유감각 (크기), 접촉 전 전기 응답 = 재질
    "r_can": (30.0, [CYL(-150.0)], "scn"), "r_rod": (46.0, [ROD], "scn"),
    "r_block": (30.0, [BLOCK], "scn"), "r_egg": (40.0, [("egg", -82.0, 22.0)], "scn"),
    "o_can": (None, [CYL(-150.0)], "scn"), "o_rod": (None, [ROD], "scn"),
    "o_block": (None, [BLOCK], "scn"), "o_egg": (None, [("egg", -82.0, 22.0)], "scn"),
    "b_slow": (0.0, [WRIST_H], "scn"), "b_contact": (15.0, [WRIST_H], "scn"),
    "b_interact": (17.0, [WRIST_H], "scn"), "b_release": (0.0, [("wrist", -118.0, 32.0, True)], "scn"),
}
CAMS = {"pose": ((-150, -230, -10), -72, 36), "side": ((-215, -195, 0), -72, 36), "scn": ((-205, -235, -70), -128, 30),
        "scn_lo": ((-225, -265, -85), -160, 28)}


def seg(p0, p1, r0, r1, m, verts=64):
    """p0 (반지름 r0) → p1 (r1) 원뿔대."""
    p0, p1 = Vector(p0), Vector(p1)
    bpy.ops.mesh.primitive_cone_add(radius1=r0, radius2=r1, depth=(p1 - p0).length, location=(p0 + p1) / 2, vertices=verts)
    c = bpy.context.object
    c.rotation_mode, c.rotation_quaternion = "QUATERNION", (p1 - p0).to_track_quat("Z", "Y")
    c.data.materials.append(m); bpy.ops.object.shade_smooth()
    return c


def hammer(hc, hand, mats):
    """망치 (그림용 비율): 강철 머리 축 y, 반지름 30 (패드가 x = ±30 에서 닿음), 나무 손잡이 아래로. hand = 손잡이 아래를 쥔 손 + 팔."""
    seg((0, -45, hc), (0, 15, hc), 30, 30, mats["metal"])                     # 머리
    seg((0, -57, hc), (0, -45, hc), 27, 31, mats["metal"])                    # 때리는 면 (모따기)
    seg((0, 15, hc), (0, 72, hc), 27, 7, mats["metal"])                       # 뒤쪽 (가늘어짐)
    seg((0, 0, hc - 25), (0, 0, hc - 185), 10.5, 12.5, mats["wood"])          # 손잡이
    seg((0, 0, hc - 105), (0, 0, hc - 188), 14, 14, mats["grip"])             # 고무 그립
    if hand:
        fz = hc - 150
        bpy.ops.mesh.primitive_uv_sphere_add(radius=26, location=(6, -2, fz), segments=64, ring_count=32)
        f = bpy.context.object; f.scale = (1.0, 0.95, 1.25); f.data.materials.append(mats["skin"]); bpy.ops.object.shade_smooth()
        seg((-14, -22, fz + 6), (-6, -24, fz + 30), 8, 7, mats["skin"], 32)    # 엄지 (손잡이 앞을 감쌈)
        d = Vector((1.0, -0.2, -0.3)).normalized()
        seg((6, -2, fz), Vector((6, -2, fz)) + d * 200, 24, 32, mats["skin"])  # 팔뚝 (오른쪽으로)


def add_object(o, mats):
    kind = o[0]
    if kind == "hammer":
        hammer(o[1], o[2], mats)
    elif kind == "egg":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=o[2], location=(0, 0, o[1]), segments=64, ring_count=32)
        e = bpy.context.object; e.scale = (1, 1, 1.28); e.data.materials.append(mats["egg"]); bpy.ops.object.shade_smooth()
    elif kind == "block":
        _, zc, hx, hy, hz = o
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, zc))
        c = bpy.context.object; c.scale = (hx, hy, hz); bpy.ops.object.transform_apply(scale=True)
        bv = c.modifiers.new("bv", "BEVEL"); bv.width, bv.segments = 3.0, 4
        c.data.materials.append(mats["wood"]); bpy.ops.object.shade_smooth()
    elif kind == "cyl":
        _, zb, r, h = o
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=(0, 0, zb + h / 2), vertices=96)
        c = bpy.context.object; c.data.materials.append(mats["metal"]); bpy.ops.object.shade_smooth()
    elif kind == "table":
        bpy.ops.mesh.primitive_cylinder_add(radius=85, depth=6, location=(0, 0, o[1] - 3), vertices=128)
        t = bpy.context.object; t.data.materials.append(mats["table"]); bpy.ops.object.shade_smooth()
    else:
        _, z, r = o[:3]
        m = mats["metal"] if kind == "rod" else mats["skin"]
        y0, y1 = (-45, 45) if kind == "rod" else (-38, 230)                   # 봉: 손가락 폭보다 조금 길게. 손목: 팔은 뒤로
        if kind == "rod":
            bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=y1 - y0, location=(0, (y0 + y1) / 2, z), rotation=(math.radians(90), 0, 0), vertices=96)
        else:                                                                 # 팔: 손목 (앞) 쪽이 가는 원뿔
            bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r * 1.25, depth=y1 - y0, location=(0, (y0 + y1) / 2, z),
                                            rotation=(math.radians(-90), 0, 0), vertices=96)
        c = bpy.context.object; c.data.materials.append(m); bpy.ops.object.shade_smooth()
        if kind == "wrist":                                                   # 주먹 (손가락 바로 앞) + 엄지
            bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(0, y0 - r * 0.6, z - r * 0.1), segments=64, ring_count=32)
            f = bpy.context.object; f.scale = (0.85, 0.72, 1.12); f.data.materials.append(m); bpy.ops.object.shade_smooth()
            bpy.ops.mesh.primitive_cylinder_add(radius=r * 0.27, depth=r * 1.0, location=(-r * 0.55, y0 - r * 0.85, z + r * 0.55),
                                                rotation=(math.radians(70), 0, math.radians(-20)), vertices=48)
            t = bpy.context.object; t.data.materials.append(m); bpy.ops.object.shade_smooth()
            if len(o) > 3 and o[3]:                                           # 망치 손잡이: 주먹을 지나 위 · 오른쪽으로 기울임 (머리는 프레임 밖으로 잘려도 됨)
                fc, d = Vector((0, y0 - r * 0.6, z - r * 0.1)), Vector((0.5, -0.12, 0.86)).normalized()
                seg(fc - d * 45, fc + d * 150, 12.5, 10.5, mats["wood"])
                seg(fc - d * 48, fc + d * 35, 14, 14, mats["grip"])
                hd, hx = fc + d * 175, Vector((1, 0, 0))
                seg(hd - hx * 45, hd + hx * 15, 30, 30, mats["metal"])
                seg(hd + hx * 15, hd + hx * 72, 27, 7, mats["metal"])


def render(name):
    bend, objs, cam_key = VARIANTS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    mats = dict(body=mat("body", (0.93, 0.93, 0.91), rough=0.45, sss=0.15),
                base=mat("base", (0.86, 0.87, 0.86), rough=0.5),
                sensor=mat("sensor", (0.50, 0.68, 0.90), rough=0.45),
                egain=mat("egain", (0.86, 0.87, 0.90), metal=1.0, rough=0.22),
                lead=mat("lead", (0.85, 0.62, 0.25), metal=1.0, rough=0.3),
                palm=mat("palm", (0.18, 0.19, 0.21), rough=0.5),
                hose=mat("hose", (0.20, 0.45, 0.80), rough=0.35),
                egg=mat("egg", (0.93, 0.80, 0.62), rough=0.55),
                metal=mat("metal", (0.62, 0.64, 0.68), metal=1.0, rough=0.38),
                skin=mat("skin", (0.88, 0.66, 0.55), rough=0.5, sss=0.2),
                table=mat("table", (0.82, 0.84, 0.87), rough=0.6),
                wood=mat("wood", (0.58, 0.38, 0.20), rough=0.55),
                grip=mat("grip", (0.15, 0.15, 0.16), rough=0.7))
    if bend is not None:                                                     # None = 물체만 (그리퍼 없음)
        finger(mats, +1, bend); finger(mats, -1, bend)
        box(-74, 74, -24, 24, 0, 14, mats["palm"])                             # 손바닥
        for sx in (+1, -1):                                                    # 공압 튜브
            tube([(sx * 55, 0, 14), (sx * 55, 0, 40), (sx * 80, 0, 70)], 2.2, mats["hose"])
    for o in objs:
        add_object(o, mats)
    loc, tz, lens = CAMS[cam_key]
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.location, cam.data.lens = loc, lens
    cam.rotation_euler = (Vector((0, 0, tz)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    for loc_, e in (((150, -200, 200), 1.2e6), ((-250, -100, 50), 5e5), ((0, 250, 150), 4e5)):
        L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA"))
        L.data.energy, L.data.size = e, 150
        L.location = loc_
        L.rotation_euler = (Vector((0, 0, -50)) - Vector(loc_)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(L)
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.4
    scn = cam_key.startswith("scn")
    sc.render.engine = "CYCLES"
    sc.cycles.samples, sc.cycles.use_denoising = (96 if scn else 160), True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = (1000, 1100) if scn else (1200, 1500)
    sc.render.filepath = str(HERE / "assets" / ("scenario" if scn else "") / f"{name}.png")
    bpy.ops.render.render(write_still=True)


names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["gripper"]
for n in (VARIANTS if names == ["all"] else names):
    render(n)
