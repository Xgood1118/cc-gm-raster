# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from raster.core import Framebuffer, Vec3, load_scene, project  # noqa: E402


def test_vec3_basic():
    a = Vec3(1, 2, 3)
    b = Vec3(2, 0, -1)
    assert a.add(b).x == 3
    assert a.sub(b).z == 4
    assert round(a.dot(b), 6) == -1
    assert round(Vec3(0, 3, 4).length(), 6) == 5


def test_framebuffer_size():
    fb = Framebuffer(10, 8)
    assert fb.width == 10
    assert fb.height == 8
    assert len(fb.pixels) == 80
    fb.set(3, 4, (9, 9, 9))
    assert fb.get(3, 4) == (9, 9, 9)


def test_load_scene_generated():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "scene.txt")
    if not os.path.exists(path):
        return
    scene = load_scene(path)
    assert scene["size"] == (320, 240)
    assert len(scene["vertices"]) >= 9
    assert len(scene["triangles"]) >= 3


def test_project_center():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "scene.txt")
    if not os.path.exists(path):
        return
    scene = load_scene(path)
    sx, sy, dz = project(Vec3(0, 0, 0), scene["camera"], 320, 240)
    assert 140 <= sx <= 180
    assert 100 <= sy <= 140
    assert dz > 0
