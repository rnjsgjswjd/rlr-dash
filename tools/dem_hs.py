# Copernicus DEM(30m) → 대시보드 좌표(EPSG:5179) 지형 음영(hillshade) 타일
#  - 평지·햇빛 받는 면은 흰색(투명 효과), 그늘만 어둡게 → 지도 위에 곱하기(multiply)로 겹침
#  - 개요 1장(300m/px) + 상세 타일(60m/px, 36km=600px), 그늘 없는 타일(바다·평지)은 건너뜀
import sys, json, base64, io, numpy as np
from osgeo import gdal
from PIL import Image
X0, Y1, U, W, H = 741111.0312999999, 2073441.1553000007, 10.0, 56791, 61983
hs_fn, dem_fn, out_fn = sys.argv[1], sys.argv[2], sys.argv[3]
hs = gdal.Open(hs_fn).ReadAsArray().astype(np.float32); dem = gdal.Open(dem_fn).ReadAsArray()
flat = float(np.median(hs[(dem <= 0.5)])) if (dem <= 0.5).any() else 181.0
v = np.clip(hs * 255.0 / max(flat, 1), 0, 255)
v = 255 - (255 - v) * 0.85  # 너무 진하지 않게
v[dem <= 0.5] = 255
img = v.astype(np.uint8); PX = 90; TP = 400
def webp(a, q):
    b = io.BytesIO(); Image.fromarray(a, "L").save(b, "WEBP", quality=q, method=6); return base64.b64encode(b.getvalue()).decode()
ovf = 4; h2, w2 = img.shape[0] // ovf * ovf, img.shape[1] // ovf * ovf
ovi = img[:h2, :w2].reshape(h2 // ovf, ovf, w2 // ovf, ovf).mean(axis=(1, 3)).astype(np.uint8)
res = {"px": PX, "tp": TP, "attrib": "지형: Copernicus DEM GLO-30 © DLR e.V. 2010-2014, © Airbus Defence and Space GmbH 2014-2018 (ESA·EU Copernicus)",
       "ov": {"px": PX * ovf, "w": ovi.shape[1], "h": ovi.shape[0], "b64": webp(ovi, 55)}, "tiles": {}}
tot = 0
for j in range(0, img.shape[0], TP):
    for i in range(0, img.shape[1], TP):
        t = img[j:j + TP, i:i + TP]
        if t.min() > 246: continue
        if t.shape != (TP, TP): t = np.pad(t, ((0, TP - t.shape[0]), (0, TP - t.shape[1])), constant_values=255)
        res["tiles"]["%d,%d" % (i // TP, j // TP)] = s = webp(t, 40); tot += len(s)
json.dump(res, open(out_fn, "w"), separators=(",", ":"))
print("flat", flat, "ov KB", len(res["ov"]["b64"]) // 1000, "tiles", len(res["tiles"]), "KB", tot // 1000)
