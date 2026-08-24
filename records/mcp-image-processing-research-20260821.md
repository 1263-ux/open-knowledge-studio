# MCP 图像处理能力研究

**研究时间**: 2026-08-21  
**目标**: 找到可以标注截图的 MCP 工具

---

## 🔍 当前可用的 MCP

### 已安装的 MCP 服务器

1. **agentkey** - 远程 API（微信、B站等）
2. **context7** - 文档查询
3. **playwright** - 浏览器自动化 ⭐
4. **tavily** - 网页搜索

**结论**: ❌ 没有专门的图像编辑 MCP

---

## 💡 可能的方案探索

### 1. Playwright 能处理图像吗？

**能做的**:
- ✅ 截图（已经在用）
- ✅ 设置视口大小
- ✅ 截取特定元素

**不能做的**:
- ❌ 在已有截图上添加标注
- ❌ 编辑 PNG 文件
- ❌ 添加红框、箭头、文字

**原因**: Playwright 是浏览器自动化工具，不是图像编辑器

---

### 2. Canvas (HTML5) 可行性

**理论上可以**:
```javascript
// 用 Canvas API 在图片上绘制
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');
const img = new Image();
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  // 绘制红框
  ctx.strokeStyle = '#FF0000';
  ctx.lineWidth = 3;
  ctx.strokeRect(100, 100, 200, 50);
  // 添加文字
  ctx.fillStyle = '#000';
  ctx.font = '14px Arial';
  ctx.fillText('标注文字', 110, 130);
};
img.src = 'screenshot.png';
```

**问题**:
1. ❌ 需要在浏览器环境运行
2. ❌ 需要将图片转为 base64 或 URL
3. ❌ 需要下载处理后的图片
4. ⚠️ 复杂，不如直接用工具

---

### 3. Python + PIL/Pillow 方案

**可以通过 Bash 调用 Python**:

```python
# image_annotate.py
from PIL import Image, ImageDraw, ImageFont

img = Image.open('input.png')
draw = ImageDraw.Draw(img)

# 红框
draw.rectangle([100, 100, 300, 150], outline='red', width=3)

# 文字
font = ImageFont.truetype('arial.ttf', 14)
draw.text((110, 130), '标注文字', fill='black', font=font)

img.save('output.png')
```

**调用**:
```bash
python image_annotate.py
```

**问题**:
- ⚠️ 需要安装 Pillow
- ⚠️ 需要为每个标注写坐标
- ⚠️ 不够直观

---

## 🎯 可行方案对比

| 方案 | 可行性 | 难度 | 推荐度 |
|------|--------|------|--------|
| **ShareX (手动)** | ✅ 完美 | 低 | ⭐⭐⭐⭐⭐ |
| **Python + Pillow** | ✅ 可行 | 中 | ⭐⭐⭐ |
| **Playwright + Canvas** | ⚠️ 复杂 | 高 | ⭐⭐ |
| **ImageMagick CLI** | ✅ 可行 | 中 | ⭐⭐⭐ |

---

## 🛠️ 推荐方案：Python + Pillow

### 安装
```bash
pip install Pillow
```

### 使用脚本

我可以写一个 Python 脚本，按照标注指南自动处理：

```python
# annotate_screenshots.py
import sys
from PIL import Image, ImageDraw, ImageFont

def annotate_oks_settings(input_path, output_path):
    img = Image.open(input_path)
    draw = ImageDraw.Draw(img)
    
    # 裁剪右侧（保留左侧 2/3）
    width, height = img.size
    img_cropped = img.crop((0, 0, width * 2 // 3, height))
    draw = ImageDraw.Draw(img_cropped)
    
    # 标注 1: Wiki 状态
    draw.rectangle([50, 150, 300, 180], outline='red', width=3)
    
    # 标注 2: 开关
    draw.ellipse([400, 250, 420, 270], outline='red', width=3)
    
    # 保存
    img_cropped.save(output_path)

if __name__ == '__main__':
    annotate_oks_settings(sys.argv[1], sys.argv[2])
```

**优点**:
- ✅ 可以自动化
- ✅ 可以批量处理
- ✅ 我可以写脚本

**缺点**:
- ⚠️ 需要精确坐标
- ⚠️ 需要先看截图确定位置

---

## 📋 决策

### 方案 A: 我写 Python 脚本（推荐）

**流程**:
1. 我先用 PIL 打开截图查看尺寸和关键位置
2. 写自动标注脚本
3. 运行脚本处理所有截图
4. 你验收效果

**时间**: 30-45 分钟

### 方案 B: 你用 ShareX 手动（最快）

**流程**:
1. 按我的标注指南
2. 手动添加红框、箭头、文字
3. 10-15 分钟完成

**时间**: 10-15 分钟

---

## ✅ 你的决定

你希望：
**A. 我写 Python 脚本自动标注**（我来做，30-45 分钟）  
**B. 你用 ShareX 手动标注**（你来做，10-15 分钟）  
**C. 先用 Python 处理简单的（裁剪），复杂标注你手动**（混合）

选哪个？
