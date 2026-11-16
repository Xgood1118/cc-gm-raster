# -*- coding: utf-8 -*-
"""软件光栅化骨架。

当前实现只把三角形顶点涂上颜色，没有覆盖三角形内部，没有深度缓冲，
也没有做屏幕裁剪。渲染结果只能当占位。
"""


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


def rasterize_triangle(fb, triangle, camera):
    """把三角形画进帧缓冲。当前只画三个顶点。"""
    pts = [project(triangle.a, camera, fb.width, fb.height),
           project(triangle.b, camera, fb.width, fb.height),
           project(triangle.c, camera, fb.width, fb.height)]
    for (sx, sy, _dz) in pts:
        x = int(round(sx))
        y = int(round(sy))
        fb.set(x, y, triangle.color)


def render(scene):
    width, height = scene["size"]
    fb = Framebuffer(width, height)
    for tri in scene["triangles"]:
        rasterize_triangle(fb, tri, scene["camera"])
    return fb


def save_png(fb, path):
    """把帧缓冲写成 PNG 文件。"""
    raise NotImplementedError("PNG 编码尚未实现")


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
