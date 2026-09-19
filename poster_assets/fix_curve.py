import re

EMU = 914400

# Same truncated-Gaussian points used in build_flowchart.js (inches)
pts = [
    (0.75, 1.75),
    (1.62, 1.95),
    (2.49, 2.373),
    (3.36, 2.724),
    (4.23, 2.895),
    (5.10, 2.95),
]
flat_end = (5.75, 2.95)

minX = pts[0][0]
minY = min(p[1] for p in pts)
maxX = flat_end[0]
maxY = max(p[1] for p in pts)


def to_local(pt):
    x, y = pt
    return (round((x - minX) * EMU), round((y - minY) * EMU))


def catmull_rom_to_bezier(p):
    n = len(p)
    segs = []
    for i in range(n - 1):
        p_prev = p[i - 1] if i - 1 >= 0 else p[i]
        p0, p1 = p[i], p[i + 1]
        p_next = p[i + 2] if i + 2 < n else p1
        c1 = (p0[0] + (p1[0] - p_prev[0]) / 6, p0[1] + (p1[1] - p_prev[1]) / 6)
        c2 = (p1[0] - (p_next[0] - p0[0]) / 6, p1[1] - (p_next[1] - p0[1]) / 6)
        segs.append((c1, c2, p1))
    return segs

segs = catmull_rom_to_bezier(pts)

path_w, path_h = round((maxX - minX) * EMU), round((maxY - minY) * EMU)
off_x, off_y = round(minX * EMU), round(minY * EMU)

lines = []
lx, ly = to_local(pts[0])
lines.append(f'<a:moveTo><a:pt x="{lx}" y="{ly}"/></a:moveTo>')
for c1, c2, p1 in segs:
    c1x, c1y = to_local(c1)
    c2x, c2y = to_local(c2)
    p1x, p1y = to_local(p1)
    lines.append(
        f'<a:cubicBezTo><a:pt x="{c1x}" y="{c1y}"/><a:pt x="{c2x}" y="{c2y}"/><a:pt x="{p1x}" y="{p1y}"/></a:cubicBezTo>'
    )
fx, fy = to_local(flat_end)
lines.append(f'<a:lnTo><a:pt x="{fx}" y="{fy}"/></a:lnTo>')
path_body = "".join(lines)

shape_xml = (
    '<p:sp>'
    '<p:nvSpPr><p:cNvPr id="100" name="GaussianDecayCurve"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
    '<p:spPr>'
    f'<a:xfrm><a:off x="{off_x}" y="{off_y}"/><a:ext cx="{path_w}" cy="{path_h}"/></a:xfrm>'
    '<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="0" b="0"/>'
    f'<a:pathLst><a:path w="{path_w}" h="{path_h}">{path_body}</a:path></a:pathLst>'
    '</a:custGeom>'
    '<a:noFill/>'
    '<a:ln w="28575" cap="rnd"><a:solidFill><a:srgbClr val="B3341F"/></a:solidFill><a:round/></a:ln>'
    '</p:spPr>'
    '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>'
    '</p:sp>'
)

slide_path = "unpacked/ppt/slides/slide1.xml"
text = open(slide_path, encoding="utf-8").read()
marker = "</p:spTree>"
assert text.count(marker) == 1
text = text.replace(marker, shape_xml + marker)
open(slide_path, "w", encoding="utf-8").write(text)
print("inserted curve shape, path bbox (EMU):", path_w, path_h, "offset:", off_x, off_y)
