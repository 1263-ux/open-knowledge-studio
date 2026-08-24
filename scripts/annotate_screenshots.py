#!/usr/bin/env python3
"""
截图自动标注脚本
根据 screenshot-annotation-guide-20260821.md 自动处理截图
"""

from PIL import Image, ImageDraw, ImageFont
import os

def load_font(size=14):
    """尝试加载字体"""
    fonts_to_try = [
        'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
        'C:/Windows/Fonts/simsun.ttc',  # 宋体
        'C:/Windows/Fonts/arial.ttf',   # Arial
    ]
    for font_path in fonts_to_try:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

def annotate_oks_settings(input_path, output_path):
    """标注 OKS 设置截图"""
    print(f"处理: {input_path}")

    img = Image.open(input_path)
    width, height = img.size
    print(f"  原始尺寸: {width}x{height}")

    # Step 1: 裁剪右侧文件列表（保留左侧 2/3）
    crop_width = int(width * 0.67)
    img_cropped = img.crop((0, 0, crop_width, height))
    print(f"  裁剪后: {crop_width}x{height}")

    # 创建绘图对象
    draw = ImageDraw.Draw(img_cropped)

    # 加载字体
    font_normal = load_font(14)
    font_bold = load_font(16)

    # Step 2: 添加标注

    # 标注 1: 知识库状态 (估算位置，需要根据实际截图调整)
    # "Wiki 8 · 审核草稿 3" 大约在顶部 1/4 位置
    y_status = int(height * 0.25)

    # 红色矩形框
    draw.rectangle(
        [50, y_status - 10, crop_width - 50, y_status + 30],
        outline='#FF0000',
        width=3
    )

    # 文字标注（白色文字 + 半透明黑色背景）
    text = "✅ 8 篇 Wiki 知识"
    text_bbox = draw.textbbox((0, 0), text, font=font_normal)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # 绘制半透明背景
    bg_padding = 5
    bg_x = 60
    bg_y = y_status + 35

    # 创建半透明层
    overlay = Image.new('RGBA', img_cropped.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [bg_x - bg_padding, bg_y - bg_padding,
         bg_x + text_width + bg_padding, bg_y + text_height + bg_padding],
        fill=(0, 0, 0, 180)
    )
    img_cropped = Image.alpha_composite(img_cropped.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img_cropped)

    # 绘制文字
    draw.text((bg_x, bg_y), text, fill='white', font=font_normal)

    # 标注 2: 自动召回开关 (估算在中间位置)
    y_switch = int(height * 0.45)

    # 箭头（简化为线条 + 三角形）
    arrow_x = 30
    arrow_y = y_switch
    draw.line([(10, arrow_y), (arrow_x, arrow_y)], fill='#FF0000', width=3)
    draw.polygon([(arrow_x, arrow_y - 5), (arrow_x, arrow_y + 5), (arrow_x + 10, arrow_y)], fill='#FF0000')

    # 文字
    text2 = "💡 一键开关"
    draw.text((arrow_x + 20, arrow_y - 10), text2, fill='#FF0000', font=font_bold)

    # 标注 3: 知识列表 (估算在下方)
    y_list = int(height * 0.65)

    # 红色矩形框
    draw.rectangle(
        [50, y_list - 10, crop_width - 50, y_list + 30],
        outline='#FF0000',
        width=3
    )

    # 文字
    text3 = "📚 真实知识"
    draw.text((60, y_list + 35), text3, fill='#FF0000', font=font_normal)

    # 保存
    img_cropped.save(output_path)
    print(f"  已保存: {output_path}")

def annotate_oks_recall_enabled(input_path, output_path):
    """标注 OKS 召回已启用截图"""
    print(f"处理: {input_path}")

    img = Image.open(input_path)
    width, height = img.size

    # 裁剪右侧
    crop_width = int(width * 0.67)
    img_cropped = img.crop((0, 0, crop_width, height))

    draw = ImageDraw.Draw(img_cropped)
    font_bold = load_font(18)

    # 标注开关状态 (估算中间位置)
    y_switch = int(height * 0.45)

    # 绿色圆圈 + 对号
    circle_x = crop_width - 100
    circle_y = y_switch
    draw.ellipse(
        [circle_x - 15, circle_y - 15, circle_x + 15, circle_y + 15],
        outline='#48BB78',
        width=4
    )

    # 绘制对号 ✅
    draw.text((circle_x - 10, circle_y - 15), '✅', fill='#48BB78', font=font_bold)

    # 文字
    text = "已启用自动召回"
    draw.text((circle_x + 25, circle_y - 10), text, fill='#48BB78', font=font_bold)

    # 保存
    img_cropped.save(output_path)
    print(f"  已保存: {output_path}")

def main():
    """主函数"""
    base_path = 'examples/oh-my-research/assets/screenshots'

    # 处理截图 1
    annotate_oks_settings(
        f'{base_path}/dsh-oks-settings.png',
        f'{base_path}/dsh-oks-settings-annotated.png'
    )

    # 处理截图 2
    annotate_oks_recall_enabled(
        f'{base_path}/dsh-oks-recall-enabled.png',
        f'{base_path}/dsh-oks-recall-enabled-annotated.png'
    )

    print("\n✅ 所有截图处理完成！")
    print("生成的文件:")
    print("  - dsh-oks-settings-annotated.png")
    print("  - dsh-oks-recall-enabled-annotated.png")

if __name__ == '__main__':
    main()
