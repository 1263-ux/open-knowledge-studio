#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
截图自动标注脚本 - 精确版本
根据实际截图尺寸调整标注位置
"""

from PIL import Image, ImageDraw, ImageFont
import sys

def load_font(size=14):
    """加载中文字体"""
    fonts = [
        'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
        'C:/Windows/Fonts/simsun.ttc',
        'C:/Windows/Fonts/arial.ttf',
    ]
    for font_path in fonts:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

def annotate_oks_settings_v2(input_path, output_path):
    """改进版 OKS 设置标注 - 基于实际尺寸 1036x850"""

    img = Image.open(input_path)
    width, height = img.size  # 1036x850

    # 裁剪右侧 (保留左侧 67%)
    crop_width = int(width * 0.67)  # 约 694px
    img_cropped = img.crop((0, 0, crop_width, height))

    # 转换为 RGBA 以支持半透明
    img_cropped = img_cropped.convert('RGBA')
    draw = ImageDraw.Draw(img_cropped)

    font_normal = load_font(14)
    font_bold = load_font(16)

    # 标注 1: 知识库状态 (位置调整到实际"Wiki 8"的位置)
    # 根据实际截图，状态栏大约在 y=180-220
    status_y = 200
    draw.rectangle(
        [20, status_y - 5, crop_width - 20, status_y + 25],
        outline='#FF0000',
        width=3
    )

    # 添加文字标注
    text1 = "8 Wiki Knowledge"
    draw.text((30, status_y + 30), text1, fill='#FF0000', font=font_bold)

    # 标注 2: 自动召回开关 (开关大约在 y=350)
    switch_y = 350
    arrow_start_x = 15
    arrow_end_x = 35

    # 绘制箭头
    draw.line([(arrow_start_x, switch_y), (arrow_end_x, switch_y)], fill='#FF0000', width=3)
    draw.polygon([
        (arrow_end_x, switch_y - 6),
        (arrow_end_x, switch_y + 6),
        (arrow_end_x + 10, switch_y)
    ], fill='#FF0000')

    text2 = "One-click Toggle"
    draw.text((50, switch_y - 10), text2, fill='#FF0000', font=font_bold)

    # 标注 3: 知识列表 (列表大约从 y=500 开始)
    list_y = 520
    draw.rectangle(
        [20, list_y - 5, crop_width - 20, list_y + 25],
        outline='#FF0000',
        width=3
    )

    text3 = "Real Knowledge Base"
    draw.text((30, list_y + 30), text3, fill='#FF0000', font=font_bold)

    # 转回 RGB 保存
    img_cropped = img_cropped.convert('RGB')
    img_cropped.save(output_path)
    print(f"OK: {output_path}")

def annotate_oks_recall_v2(input_path, output_path):
    """改进版召回启用标注"""

    img = Image.open(input_path)
    width, height = img.size

    # 裁剪
    crop_width = int(width * 0.67)
    img_cropped = img.crop((0, 0, crop_width, height))
    img_cropped = img_cropped.convert('RGBA')

    draw = ImageDraw.Draw(img_cropped)
    font_bold = load_font(18)

    # 开关位置 (假设在中间偏上)
    switch_y = 350

    # 绿色高亮圆圈
    circle_x = crop_width - 80
    circle_r = 20
    draw.ellipse(
        [circle_x - circle_r, switch_y - circle_r,
         circle_x + circle_r, switch_y + circle_r],
        outline='#48BB78',
        width=4
    )

    # 文字
    text = "Auto-Recall ON"
    draw.text((circle_x + circle_r + 10, switch_y - 12), text, fill='#48BB78', font=font_bold)

    img_cropped = img_cropped.convert('RGB')
    img_cropped.save(output_path)
    print(f"OK: {output_path}")

if __name__ == '__main__':
    base = 'examples/oh-my-research/assets/screenshots'

    annotate_oks_settings_v2(
        f'{base}/dsh-oks-settings.png',
        f'{base}/dsh-oks-settings-annotated.png'
    )

    annotate_oks_recall_v2(
        f'{base}/dsh-oks-recall-enabled.png',
        f'{base}/dsh-oks-recall-enabled-annotated.png'
    )

    print("Done!")
