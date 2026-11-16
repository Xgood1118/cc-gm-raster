# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from raster.core import (  # noqa: E402
    Framebuffer,
    Triangle,
    Vec3,
    load_scene,
    render,
    save_png,
)

CAMERA = {
    "eye": Vec3(0, 0, 10),
    "target": Vec3(0, 0, 0),
    "up": Vec3(0, 1, 0),
    "fov": 60,
}

BACKGROUND = (0, 0, 0)


def make_scene(triangles, size=(64, 48)):
    return {"size": size, "camera": CAMERA, "vertices": [], "triangles": triangles}


def count_non_background(fb):
    return sum(1 for p in fb.pixels if p != BACKGROUND)


def front_triangle(z=0.0, color=(200, 30, 30)):
    # 从相机看为逆时针（法线朝向相机）的正面三角形。
    return Triangle(Vec3(-2, -1.5, z), Vec3(2, -1.5, z), Vec3(0, 1.5, z), color)


def test_fill_interior_non_empty():
    tri = front_triangle(color=(200, 30, 30))
    fb = render(make_scene([tri]))
    n = count_non_background(fb)
    assert n > 300  # 不只是三个顶点，内部被完整覆盖
    # 三角形重心附近的像素必须是三角形颜色（内部无渐变，单色恒定）。
    cx, cy = fb.width // 2, int(fb.height * 0.55)
    assert fb.get(cx, cy) == (200, 30, 30)


def test_occlusion_near_covers_far_regardless_of_order():
    near = Triangle(Vec3(-1.5, -1.5, 3), Vec3(1.5, -1.5, 3), Vec3(0, 1.5, 3),
                    (30, 30, 220))
    far = front_triangle(z=0.0, color=(220, 30, 30))
    fb1 = render(make_scene([near, far]))
    fb2 = render(make_scene([far, near]))
    # 与绘制顺序无关
    assert fb1.pixels == fb2.pixels
    # 中心区域被近处（蓝色）三角形覆盖
    cx, cy = fb1.width // 2, fb1.height // 2
    assert fb1.get(cx, cy) == (30, 30, 220)


def test_depth_tie_keeps_first_drawn():
    # 深度完全相等时保留先画的三角形（规则见 README）。
    t1 = front_triangle(z=0.0, color=(10, 200, 10))
    t2 = front_triangle(z=0.0, color=(200, 10, 200))
    fb = render(make_scene([t1, t2]))
    cx, cy = fb.width // 2, int(fb.height * 0.55)
    assert fb.get(cx, cy) == (10, 200, 10)


def test_clipping_out_of_bounds_no_exception():
    # 顶点远远落在画面外，且部分覆盖画面：只画画面内的部分，不抛异常。
    tri = Triangle(Vec3(-100, -100, 1), Vec3(100, -100, 1), Vec3(0, 100, 1),
                   (20, 200, 20))
    fb = render(make_scene([tri]))
    assert count_non_background(fb) > 0
    # 完全在画面外的三角形：不抛异常，也不写入任何像素。
    outside = Triangle(Vec3(-1000, -1000, 1), Vec3(-999, -1000, 1),
                       Vec3(-1000, -999, 1), (1, 2, 3))
    fb2 = render(make_scene([outside]))
    assert count_non_background(fb2) == 0


def test_backface_not_drawn():
    back = Triangle(Vec3(0, 1.5, 0), Vec3(2, -1.5, 0), Vec3(-2, -1.5, 0),
                    (240, 240, 30))  # 与 front_triangle 顶点顺序相反
    fb = render(make_scene([back]))
    assert count_non_background(fb) == 0
    # 同一组顶点换成正面朝向就能画出来（对照）。
    fb_front = render(make_scene([front_triangle(z=0.0)]))
    assert count_non_background(fb_front) > 0


def test_render_twice_identical(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scene = load_scene(os.path.join(root, "data", "scene.txt"))
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    save_png(render(scene), str(p1))
    save_png(render(scene), str(p2))
    assert p1.read_bytes() == p2.read_bytes()


def test_png_dimensions_match_scene(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scene = load_scene(os.path.join(root, "data", "scene.txt"))
    fb = render(scene)
    assert (fb.width, fb.height) == scene["size"]
    out = tmp_path / "scene.png"
    save_png(fb, str(out))
    data = out.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR 中的宽高与场景一致
    import struct
    w, h = struct.unpack(">II", data[16:24])
    assert (w, h) == scene["size"]
