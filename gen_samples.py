# -*- coding: utf-8 -*-
"""生成场景文件：两块相交的三角形与一块更远的三角形。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    scene = """size 320 240
camera 0 0 6 0 0 0 0 1 0 60
v -2 -1.5 0
v 2 -1.5 0
v 0 1.5 0
v -1.2 0 2
v 1.2 0 2
v 0 1.6 2
v -1 1 -3
v 1 1 -3
v 0 -1.5 -3
v -0.4 -0.4 0.2
v 0.4 -0.4 0.2
v 0 -0.4 1.2
tri 0 1 2 220 90 60
tri 3 4 5 60 140 220
tri 6 7 8 90 200 120
tri 9 10 11 240 220 80
"""
    path = os.path.join(HERE, "data", "scene.txt")
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(scene)
    print("已生成", path)


if __name__ == "__main__":
    main()
