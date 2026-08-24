#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业级截图标注 - 按用户要求：醒目红框、粗箭头、清晰文字
"""

from PIL import Image, ImageDraw, ImageFont
import os

def load_font(size=16):
    fonts = [
        'C:/Windows/Fonts/msyhbd.ttc',  # 微软雅黑粗体
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/arialbd.ttf',  # Arial Bold
    ]
    for font_path in fonts:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

def draw_arrow(draw, start_x, start_y, end_x, end_y, color='#FF0000', width=5):
    """绘制粗箭头"""
    # 主线
    draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)

    # 箭头头部（三角形）
    import math
    angle = math.atan2(end_y - start_y, end_x - start_x)
    arrow_length = 20
    arrow_angle = math.pi / 6

    # 左侧三角
    x1 = end_x - arrow_length * math.cos(angle - arrow_angle)
    y1 = end_y - arrow_length * math.sin(angle - arrow_angle)

    # 右侧三角
    x2 = end_x - arrow_length * math.cos(angle + arrow_angle)
    y2 = end_y - arrow_length * math.sin(angle + arrow_angle)

    draw.polygon([(end_x, end_y), (x1, y1), (x2, y2)], fill=color)

def draw_text_with_bg(draw, text, x, y, font, text_color='white', bg_color='#000000', padding=8):
    """绘制带半透明背景的文字"""
    # 获取文字边界
    bbox = draw.textbbox((x, y), text, font=font)

    # 绘制半透明背景
    bg_box = [
        bbox[0] - padding,
        bbox[1] - padding,
        bbox[2] + padding,
        bbox[3] + padding
    ]
    draw.rectangle(bg_box, fill=bg_color + 'CC')  # CC = 80% opacity

    # 绘制文字
    draw.text((x, y), text, fill=text_color, font=font)

def annotate_oks_settings_final(input_path, output_path):
    """最终版 OKS 设置标注 - 专业级"""

    img = Image.open(input_path)
    width, height = img.size

    # 裁剪右侧
    crop_width = int(width * 0.67)
    img = img.crop((0, 0, crop_width, height))
    img = img.convert('RGBA')

    # 创建绘图层
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_large = load_font(20)
    font_medium = load_font(16)

    # 标注 1: Wiki 状态 (实际位置 y≈200)
    box1_y = 200
    draw.rectangle(
        [15, box1_y - 5, crop_width - 15, box1_y + 30],
        outline='#FF0000',
        width=5
    )
    draw_text_with_bg(draw, '✅ 8 Wiki Knowledge', 25, box1_y + 40, font_large, '#FFFFFF', '#FF0000')

    # 标注 2: 开关 + 箭头 (y≈350)
    switch_y = 350
    draw_arrow(draw, 20, switch_y, 60, switch_y, '#FF0000', 6)
    draw_text_with_bg(draw, '💡 One-Click Toggle', 70, switch_y - 12, font_large, '#FFFFFF', '#FF0000')

    # 标注 3: 知识列表 (y≈520)
    list_y = 520
    draw.rectangle(
        [15, list_y - 5, crop_width - 15, list_y + 30],
        outline='#48BB78',
        width=5
    )
    draw_text_with_bg(draw, '📚 Real Knowledge Base', 25, list_y + 40, font_large, '#FFFFFF', '#48BB78')

    # 合并图层
    img = Image.alpha_composite(img, overlay).convert('RGB')
    img.save(output_path, quality=95)
    print(f"✓ {os.path.basename(output_path)}")

def annotate_oks_recall_final(input_path, output_path):
    """最终版召回启用标注"""

    img = Image.open(input_path)
    width, height = img.size

    crop_width = int(width * 0.67)
    img = img.crop((0, 0, crop_width, height))
    img = img.convert('RGBA')

    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_large = load_font(22)

    # 开关位置
    switch_y = 350

    # 绿色高亮圆圈 + 箭头
    circle_x = crop_width - 100
    draw_arrow(draw, circle_x - 80, switch_y, circle_x - 30, switch_y, '#48BB78', 6)

    draw.ellipse(
        [circle_x - 25, switch_y - 25, circle_x + 25, switch_y + 25],
        outline='#48BB78',
        width=6
    )

    # 大号文字
    draw_text_with_bg(draw, '✅ Auto-Recall ON', circle_x + 35, switch_y - 14, font_large, '#FFFFFF', '#48BB78')

    img = Image.alpha_composite(img, overlay).convert('RGB')
    img.save(output_path, quality=95)
    print(f"✓ {os.path.basename(output_path)}")

def annotate_conversation_final(input_path, output_path):
    """最终版对话标注 - 突出 OKS 召回和成本"""

    img = Image.open(input_path)
    width, height = img.size
    img = img.convert('RGBA')

    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_large = load_font(20)

    # 标注 1: OKS 上下文注入 (顶部)
    oks_y = 100
    draw.rectangle(
        [20, oks_y, 250, oks_y + 40],
        outline='#48BB78',
        width=5
    )
    draw_text_with_bg(draw, '🔍 OKS Auto-Recall', 30, oks_y + 10, font_large, '#FFFFFF', '#48BB78')

    # 标注 2: 成本分析区域 (中下部)
    cost_y = int(height * 0.6)
    draw.rectangle(
        [width - 350, cost_y, width - 50, cost_y + 80],
        outline='#FF0000',
        width=5
    )
    draw_text_with_bg(draw, '💰 Cost Analysis', width - 330, cost_y + 90, font_large, '#FFFFFF', '#FF0000')

    img = Image.alpha_composite(img, overlay).convert('RGB')
    img.save(output_path, quality=95)
    print(f"✓ {os.path.basename(output_path)}")

if __name__ == '__main__':
    base = 'examples/oh-my-research/assets/screenshots'

    print("Processing screenshots with professional annotations...")

    annotate_oks_settings_final(
        f'{base}/dsh-oks-settings.png',
        f'{base}/dsh-oks-settings-annotated.png'
    )

    annotate_oks_recall_final(
        f'{base}/dsh-oks-recall-enabled.png',
        f'{base}/dsh-oks-recall-enabled-annotated.png'
    )

    annotate_conversation_final(
        f'{base}/dsh-oks-agent-full-response.png',
        f'{base}/dsh-oks-conversation-annotated.png'
    )

    print("\n✅ All screenshots processed!")
