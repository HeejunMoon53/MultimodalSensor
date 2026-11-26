"""사진형 렌더용 소품 (보이기만 함: contype = conaffinity = 0, group 2 → 물리·근접 거리 불변, tests/test_photo.py).

hammer: 사람이 쥔 망치의 금속 자루가 잡을 물체 (도체). 물리 원기둥(축 y, r 15 mm) = 자루 가운데.
wrist : 망치를 쥔 사람의 손목이 잡을 물체 (인체). 물리 원기둥 = 손목, 손은 −y 쪽에서 망치를 세워 쥔다 (머리가 아래).
"""
import numpy as np

SKIN = "0.85 0.62 0.55 1"   # plant.py 인체 패드와 같은 색
V = ' contype="0" conaffinity="0" group="2"'


def _cam(pos, target):
    f = np.subtract(target, pos); f = f / np.linalg.norm(f)
    x = np.cross(f, [0, 0, 1]); x /= np.linalg.norm(x)
    y = np.cross(x, f)
    return " ".join(f"{v:.4f}" for v in (*x, *y))


def deco(kind):
    """→ (asset, visual, world, obj) MJCF 조각."""
    asset = ('<asset><texture name="sky" type="skybox" builtin="gradient" rgb1="0.93 0.95 0.98" rgb2="0.55 0.62 0.72" width="256" height="256"/>'
             '<texture name="fl" type="2d" builtin="checker" rgb1="0.82 0.82 0.80" rgb2="0.72 0.72 0.70" width="256" height="256"/>'
             '<material name="floor" texture="fl" texrepeat="12 12" reflectance="0.15"/>'
             '<material name="steel" rgba="0.62 0.64 0.68 1" specular="0.9" shininess="0.8" reflectance="0.3"/>'
             '<material name="dark" rgba="0.25 0.26 0.28 1" specular="0.8" shininess="0.7" reflectance="0.2"/>'
             f'<material name="skin" rgba="{SKIN}" specular="0.2" shininess="0.3"/>'
             '<material name="grip" rgba="0.75 0.15 0.12 1" specular="0.3"/>'
             '<material name="wood" rgba="0.62 0.42 0.24 1" specular="0.2"/>'
             '<material name="sleeve" rgba="0.22 0.33 0.52 1" specular="0.1"/></asset>')
    visual = '<headlight ambient="0.35 0.35 0.35" diffuse="0.5 0.5 0.5"/><quality shadowsize="4096"/>'
    pos, tgt = (0.26, -0.40, 0.17), (0.0, 0.0, -0.09)   # 위에서 비스듬히: 손·망치 머리가 그리퍼를 가리지 않게
    world = (f'<geom type="plane" size="2 2 0.01" pos="0 0 -0.75" material="floor"{V}/>'
             '<light pos="0.3 -0.4 0.6" dir="-0.4 0.5 -1" castshadow="true" diffuse="0.6 0.6 0.6"/>'
             f'<camera name="photo" pos="{pos[0]} {pos[1]} {pos[2]}" xyaxes="{_cam(pos, tgt)}" fovy="42"/>')
    if kind == "hammer":
        obj = (f'<geom type="cylinder" fromto="0 -0.15 0 0 -0.04 0" size="0.015" material="steel"{V}/>'
               f'<geom type="cylinder" fromto="0 0.04 0 0 0.10 0" size="0.015" material="steel"{V}/>'
               f'<geom type="cylinder" fromto="0 0.10 0 0 0.19 0" size="0.0175" material="grip"{V}/>'
               f'<geom type="box" pos="0 -0.165 0" size="0.055 0.021 0.023" material="dark"{V}/>'
               f'<geom type="cylinder" fromto="0.055 -0.165 0 0.072 -0.165 0" size="0.021" material="dark"{V}/>'
               f'<geom type="capsule" fromto="-0.055 -0.165 0.005 -0.085 -0.165 0.025" size="0.009" material="dark"{V}/>'
               f'<geom type="ellipsoid" pos="0 0.15 -0.004" size="0.033 0.042 0.031" material="skin"{V}/>'
               f'<geom type="capsule" fromto="0.022 0.125 0.018 0.004 0.118 0.032" size="0.0095" material="skin"{V}/>'
               f'<geom type="capsule" fromto="0 0.16 -0.03 0.01 0.18 -0.24" size="0.027" material="skin"{V}/>'
               f'<geom type="cylinder" fromto="0.01 0.18 -0.22 0.016 0.19 -0.45" size="0.036" material="sleeve"{V}/>')
    elif kind == "wrist":
        obj = (f'<geom type="capsule" fromto="0 0.035 0 0 0.12 -0.004" size="0.0165" material="skin"{V}/>'
               f'<geom type="capsule" fromto="0 0.10 -0.003 0 0.27 -0.02" size="0.025" material="skin"{V}/>'
               f'<geom type="cylinder" fromto="0 0.25 -0.018 0 0.45 -0.035" size="0.034" material="sleeve"{V}/>'
               f'<geom type="capsule" fromto="0 -0.035 0 0 -0.05 0" size="0.0165" material="skin"{V}/>'
               f'<geom type="ellipsoid" pos="0 -0.078 0" size="0.031 0.036 0.036" material="skin"{V}/>'
               f'<geom type="capsule" fromto="0.024 -0.062 0.02 0.012 -0.09 0.03" size="0.0095" material="skin"{V}/>'
               f'<geom type="cylinder" fromto="0 -0.08 0.03 0 -0.08 -0.2" size="0.013" material="wood"{V}/>'
               f'<geom type="box" pos="0 -0.08 -0.215" size="0.05 0.019 0.02" material="dark"{V}/>'
               f'<geom type="cylinder" fromto="0.05 -0.08 -0.215 0.066 -0.08 -0.215" size="0.019" material="dark"{V}/>')
    else:
        raise ValueError(kind)
    return asset, visual, world, obj
