# -*- coding: utf-8 -*-
"""软件光栅化器。

功能：三角形填充（重心坐标插值顶点颜色）、深度缓冲、屏幕裁剪、
背面剔除、超采样抗锯齿、PNG 输出。仅使用 Python 标准库。

判定规则（README 中有同样说明）：

- 背面剔除：令 n = (b - a) x (c - a)，若 n · (eye - a) <= 0，
  即三角形法线背向相机（或三角形退化、面积为零），则不绘制。
- 深度：深度缓冲保存透视插值后的 1/z，值大者离相机近。
  新片元严格大于缓冲值才覆盖；深度相等时保留先画的三角形。
- 裁剪：扫描线包围盒在光栅化前裁剪到帧缓冲范围内，
  画面外的像素一律不写入。
- 抗锯齿：以 SUPERSAMPLE 倍分辨率渲染，再盒式滤波下采样。
"""

import binascii
import math
import struct
import zlib

# 超采样抗锯齿倍数：每个输出像素按 SUPERSAMPLE x SUPERSAMPLE 个子像素渲染。
SUPERSAMPLE = 3


class Vec3(object):
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def add(self, o):
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def sub(self, o):
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def scale(self, k):
        return Vec3(self.x * k, self.y * k, self.z * k)

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o):
        return Vec3(self.y * o.z - self.z * o.y,
                    self.z * o.x - self.x * o.z,
                    self.x * o.y - self.y * o.x)

    def length(self):
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5

    def normalized(self):
        n = self.length()
        if n == 0:
            return Vec3(0, 0, 0)
        return self.scale(1.0 / n)

    def __repr__(self):
        return "Vec3(%.3f, %.3f, %.3f)" % (self.x, self.y, self.z)


class Triangle(object):
    def __init__(self, a, b, c, color):
        self.a = a
        self.b = b
        self.c = c
        self.color = color


def load_scene(path):
    """读取场景文件。

    行格式：
      size W H
      camera ex ey ez tx ty tz ux uy uz fov
      v x y z           顶点，索引按出现顺序从 0 开始
      tri i j k r g b   三角形，顶点索引 + 颜色
    """
    verts = []
    tris = []
    size = (320, 240)
    camera = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            tag = parts[0]
            if tag == "size":
                size = (int(parts[1]), int(parts[2]))
            elif tag == "camera":
                camera = {
                    "eye": Vec3(float(parts[1]), float(parts[2]), float(parts[3])),
                    "target": Vec3(float(parts[4]), float(parts[5]), float(parts[6])),
                    "up": Vec3(float(parts[7]), float(parts[8]), float(parts[9])),
                    "fov": float(parts[10]),
                }
            elif tag == "v":
                verts.append(Vec3(float(parts[1]), float(parts[2]), float(parts[3])))
            elif tag == "tri":
                tris.append(Triangle(verts[int(parts[1])], verts[int(parts[2])],
                                     verts[int(parts[3])],
                                     (int(parts[4]), int(parts[5]), int(parts[6]))))
            else:
                raise ValueError("未知行: %s" % line)
    return {"size": size, "camera": camera, "vertices": verts, "triangles": tris}


class Framebuffer(object):
    def __init__(self, width, height, background=(0, 0, 0)):
        self.width = int(width)
        self.height = int(height)
        self.pixels = [background for _ in range(self.width * self.height)]
        # 深度缓冲，存放 1/z（透视插值），0 表示尚未写入（无穷远）。
        self.depth = [0.0] * (self.width * self.height)

    def set(self, x, y, color):
        self.pixels[y * self.width + x] = color

    def get(self, x, y):
        return self.pixels[y * self.width + x]


def project(v, camera, width, height):
    """把世界坐标投影到屏幕坐标，返回 (x, y, depth)。"""
    forward = camera["target"].sub(camera["eye"]).normalized()
    right = forward.cross(camera["up"]).normalized()
    up = right.cross(forward)
    rel = v.sub(camera["eye"])
    cx = rel.dot(right)
    cy = rel.dot(up)
    cz = rel.dot(forward)
    if cz <= 0.0001:
        cz = 0.0001
    f = 1.0 / (cz * 2.0 * (camera["fov"] / 360.0))
    sx = width / 2.0 + cx * f * width / 2.0
    sy = height / 2.0 - cy * f * height / 2.0
    return (sx, sy, cz)


def _vertex_colors(color):
    """把三角形颜色规格化成三个顶点颜色。

    color 可以是单个 (r, g, b)（广播到三个顶点），
    也可以是 ((r, g, b), (r, g, b), (r, g, b)) 的逐顶点颜色。
    """
    if isinstance(color[0], (tuple, list)):
        return color[0], color[1], color[2]
    return color, color, color


def _to_byte(v):
    v = int(v + 0.5)
    if v < 0:
        return 0
    if v > 255:
        return 255
    return v


def rasterize_triangle(fb, triangle, camera):
    """把三角形光栅化进帧缓冲（含深度测试、裁剪、背面剔除）。"""
    a = triangle.a
    b = triangle.b
    c = triangle.c

    # 背面剔除：法线背向相机（或退化）的三角形不绘制。
    normal = b.sub(a).cross(c.sub(a))
    if normal.dot(camera["eye"].sub(a)) <= 0.0:
        return

    (x0, y0, z0) = project(a, camera, fb.width, fb.height)
    (x1, y1, z1) = project(b, camera, fb.width, fb.height)
    (x2, y2, z2) = project(c, camera, fb.width, fb.height)

    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if den == 0.0:
        return  # 投影后退化（面积为 0）

    c0, c1, c2 = _vertex_colors(triangle.color)
    iz0 = 1.0 / z0
    iz1 = 1.0 / z1
    iz2 = 1.0 / z2

    # 屏幕空间包围盒，裁剪到帧缓冲范围内。
    min_x = max(0, int(math.floor(min(x0, x1, x2))))
    max_x = min(fb.width - 1, int(math.ceil(max(x0, x1, x2))))
    min_y = max(0, int(math.floor(min(y0, y1, y2))))
    max_y = min(fb.height - 1, int(math.ceil(max(y0, y1, y2))))
    if min_x > max_x or min_y > max_y:
        return

    inv_den = 1.0 / den
    # 重心坐标 w0、w1 关于 x、y 的增量（w2 = 1 - w0 - w1）。
    a0 = (y1 - y2) * inv_den
    b0 = (x2 - x1) * inv_den
    a1 = (y2 - y0) * inv_den
    b1 = (x0 - x2) * inv_den

    # 1/z 与顶点颜色都按重心坐标插值，同样是关于 x、y 的线性函数。
    diz0 = iz0 - iz2
    diz1 = iz1 - iz2
    dr0 = c0[0] - c2[0]
    dr1 = c1[0] - c2[0]
    dg0 = c0[1] - c2[1]
    dg1 = c1[1] - c2[1]
    db0 = c0[2] - c2[2]
    db1 = c1[2] - c2[2]

    start_x = min_x + 0.5
    start_y = min_y + 0.5
    # (min_x, min_y) 像素中心处的起始值。
    w0_row = a0 * (start_x - x2) + b0 * (start_y - y2)
    w1_row = a1 * (start_x - x2) + b1 * (start_y - y2)

    pixels = fb.pixels
    depth = fb.depth
    width = fb.width

    for y in range(min_y, max_y + 1):
        w0 = w0_row
        w1 = w1_row
        idx = y * width + min_x
        for x in range(min_x, max_x + 1):
            if w0 >= 0.0 and w1 >= 0.0 and w0 + w1 <= 1.0:
                iz = iz2 + w0 * diz0 + w1 * diz1
                if iz > depth[idx]:
                    depth[idx] = iz
                    pixels[idx] = (
                        _to_byte(c2[0] + w0 * dr0 + w1 * dr1),
                        _to_byte(c2[1] + w0 * dg0 + w1 * dg1),
                        _to_byte(c2[2] + w0 * db0 + w1 * db1),
                    )
            w0 += a0
            w1 += a1
            idx += 1
        w0_row += b0
        w1_row += b1


def render(scene):
    """渲染整个场景，返回场景尺寸的帧缓冲。

    内部按 SUPERSAMPLE 倍分辨率渲染再做盒式滤波下采样，
    以消除斜边的硬锯齿。
    """
    width, height = scene["size"]
    ss = SUPERSAMPLE
    hi = Framebuffer(width * ss, height * ss)
    for tri in scene["triangles"]:
        rasterize_triangle(hi, tri, scene["camera"])

    fb = Framebuffer(width, height)
    n = ss * ss
    half = n // 2
    for y in range(height):
        for x in range(width):
            r = g = b = 0
            base_y = y * ss
            base_x = x * ss
            for dy in range(ss):
                row = (base_y + dy) * hi.width + base_x
                for dx in range(ss):
                    p = hi.pixels[row + dx]
                    r += p[0]
                    g += p[1]
                    b += p[2]
            fb.pixels[y * width + x] = ((r + half) // n,
                                        (g + half) // n,
                                        (b + half) // n)
    return fb


def _png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF))


def save_png(fb, path):
    """把帧缓冲写成 8 位 RGB PNG 文件（无时间戳，输出逐字节确定）。"""
    raw = bytearray()
    for y in range(fb.height):
        raw.append(0)  # 每行滤波类型 0（None）
        row = y * fb.width
        for x in range(fb.width):
            raw.extend(bytes(fb.pixels[row + x]))
    ihdr = struct.pack(">IIBBBBB", fb.width, fb.height, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + _png_chunk(b"IHDR", ihdr)
           + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _png_chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="raster")
    ap.add_argument("scene")
    ap.add_argument("--out", default="out.png")
    args = ap.parse_args(argv)
    scene = load_scene(args.scene)
    fb = render(scene)
    save_png(fb, args.out)
    print("渲染完成: %s (%dx%d)" % (args.out, fb.width, fb.height))
    return 0
