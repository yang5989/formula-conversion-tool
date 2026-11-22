"""
生成程序图标。

设计：深蓝圆形底 + 白色 Σ 符号 + 右下角转换箭头
寓意：公式（Σ）经过转换（箭头）变成可用格式。
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QGuiApplication, QIcon, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap,
)

# 输出到项目根的 assets/（相对本脚本定位，跨机器可用）
OUT_DIR = Path(__file__).resolve().parent.parent / 'assets'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_icon(size: int) -> QPixmap:
    """在 size×size 的画布上绘制图标：深蓝圆底 + 白色 Σ"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    s = size

    # ---------- 圆形底：深蓝渐变 ----------
    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0.0, QColor('#1f6feb'))      # 亮蓝
    grad.setColorAt(1.0, QColor('#0d3b7a'))      # 深蓝
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(1, 1, s - 2, s - 2))

    # ---------- 内圈细描边（增加质感） ----------
    if s >= 32:
        pen = QPen(QColor(255, 255, 255, 60), max(1.0, s * 0.015))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        inset = s * 0.09
        p.drawEllipse(QRectF(inset, inset, s - inset * 2, s - inset * 2))

    # ---------- Σ 符号（主角，居中） ----------
    font = QFont('Cambria Math')
    if not font.exactMatch():
        font = QFont('Times New Roman')
    font.setBold(True)
    # 无箭头后可以放大一些，占满视觉重心
    font.setPixelSize(int(s * 0.65))
    p.setFont(font)
    p.setPen(QColor('#ffffff'))
    p.drawText(QRect(0, 0, s, s), Qt.AlignCenter, 'Σ')

    p.end()
    return pm


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)

    # ---- 生成多种尺寸的 PNG ----
    sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    pixmaps = []
    for sz in sizes:
        pm = make_icon(sz)
        pixmaps.append(pm)
        if sz in (256, 512):
            path = OUT_DIR / f'icon-{sz}.png'
            pm.save(str(path), 'PNG')
            print(f'  {path.name}  {path.stat().st_size} bytes')

    # ---- 主图标（256，程序窗口用） ----
    main_pm = make_icon(256)
    main_pm.save(str(OUT_DIR / 'icon.png'), 'PNG')
    print(f'  icon.png')

    # ---- 多尺寸 ICO（Windows 专用，含所有尺寸） ----
    try:
        from PIL import Image
        images = []
        for sz in sizes:
            p = OUT_DIR / f'_tmp_{sz}.png'
            make_icon(sz).save(str(p), 'PNG')
            images.append(Image.open(str(p)))
            images[-1].load()          # 立刻读进内存，之后好删文件

        # 用最大尺寸当基准，sizes 指定包含的多分辨率
        images[-1].save(
            str(OUT_DIR / 'icon.ico'),
            format='ICO',
            sizes=[(sz, sz) for sz in sizes],
        )
        for im in images:
            im.close()
        for sz in sizes:
            (OUT_DIR / f'_tmp_{sz}.png').unlink(missing_ok=True)
        ico = OUT_DIR / 'icon.ico'
        print(f'  icon.ico  {ico.stat().st_size} bytes')
    except ImportError:
        print('  [跳过 ico] 需要 Pillow')
    except Exception as e:
        print(f'  [ico 失败] {e}')
        # 清理残留
        for sz in sizes:
            try:
                (OUT_DIR / f'_tmp_{sz}.png').unlink(missing_ok=True)
            except Exception:
                pass

    # ---- 预览图（把各尺寸拼一起，方便肉眼检查） ----
    preview_w = sum(sizes) + 20 * (len(sizes) - 1) + 40
    preview = QPixmap(preview_w, 300)
    preview.fill(QColor('#0d1117'))
    pp = QPainter(preview)
    x = 20
    for sz, pm in zip(sizes, pixmaps):
        pp.drawPixmap(x, (300 - sz) // 2, pm)
        x += sz + 20
    pp.end()
    preview.save(str(OUT_DIR / '_preview.png'), 'PNG')
    print(f'  _preview.png（各尺寸预览）')


if __name__ == '__main__':
    main()
