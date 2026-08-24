#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理 DSH 对话截图 - 标注 OKS 召回和成本分析
"""

from PIL import Image, ImageDraw, ImageFont

def load_font(size=14):
    fonts = [
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/arial.ttf',
    ]
    for font_path in fonts:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

def annotate_dsh_conversation(input_path, output_path):
    """标注 DSH 对话截图 - 突出 OKS 召回和成本数字"""

    img = Image.open(input_path)
    width, height = img.size

    img = img.convert('RGBA')
    draw = ImageDraw.Draw(img)

    font_normal = load_font(14)
    font_bold = load_font(18)

    # 标注 1: OKS 上下文注入提示 (假设在顶部)
    oks_y = 80
    draw.rectangle(
        [20, oks_y, 200, oks_y + 30],
        outline='#48BB78',
        width=3
    )
    text1 = "OKS Auto-Recall"
    draw.text((30, oks_y + 35), text1, fill='#48BB78', font=font_bold)

    # 标注 2: 成本数字区域 (假设在中间)
    cost_y = int(height * 0.5)
    draw.rectangle(
        [width - 250, cost_y, width - 50, cost_y + 60],
        outline='#FF0000',
        width=3
    )
    text2 = "Cost Analysis"
    draw.text((width - 240, cost_y + 65), text2, fill='#FF0000', font=font_bold)

    img = img.convert('RGB')
    img.save(output_path)
    print(f"OK: {output_path}")

if __name__ == '__main__':
    base = 'examples/oh-my-research/assets/screenshots'

    # 处理最终回答截图
    annotate_dsh_conversation(
        f'{base}/dsh-oks-agent-full-response.png',
        f'{base}/dsh-oks-conversation-annotated.png'
    )

    print("Done!")
