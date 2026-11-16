# 软件光栅化器

这是骨架版本。`raster/core.py` 目前只做三件事：解析场景文件、把三角形顶点涂色、
提供帧缓冲容器。

## 已知缺口

- `rasterize_triangle` 只在三个顶点上落像素，三角形内部是空的。
- 没有深度缓冲，三角形互相遮挡时结果依赖绘制顺序。
- 没有任何屏幕边界检查，投影落在画面外的顶点会用负下标写进帧缓冲，
  实际表现是画面另一侧出现杂点甚至抛 IndexError。
- 没有背面剔除，背向相机的三角形同样会被画出来。
- `save_png` 直接抛 NotImplementedError，产不出图片。
- 没有抗锯齿，斜边是硬锯齿。

## 运行

```
python gen_samples.py
python -m raster.cli data/scene.txt --out out.png
python -m pytest tests -q
```

## 场景文件格式

```
size W H
camera ex ey ez tx ty tz ux uy uz fov
v x y z
tri i j k r g b
```

`scene.txt` 里有两块相交的三角形、一块更远的背景三角形，还有一块夹在中间的小三角形。
