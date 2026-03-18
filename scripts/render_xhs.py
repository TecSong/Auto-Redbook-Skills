#!/usr/bin/env python3
"""
小红书卡片渲染脚本 - 增强版 v2
支持多种排版样式、封面布局和智能分页策略

使用方法:
    python render_xhs.py <markdown_file> [options]

选项:
    --output-dir, -o     输出目录（默认为当前工作目录）
    --theme, -t          排版主题：default, playful-geometric, neo-brutalism,
                         botanical, professional, retro, terminal, sketch,
                         xiaohongshu, magazine, glassmorphism, gradient-pop, dark-elegant
    --cover, -c          封面布局：classic, centered, full, split, poster
    --mode, -m           分页模式：
                         - separator  : 按 --- 分隔符手动分页（默认）
                         - auto-fit   : 自动缩放文字以填满固定尺寸
                         - auto-split : 根据内容高度自动切分
                         - dynamic    : 根据内容动态调整图片高度
    --width, -w          图片宽度（默认 1080）
    --height             图片高度（默认 1440，dynamic 模式下为最小高度）
    --max-height         dynamic 模式下的最大高度（默认 4320）
    --dpr                设备像素比（默认 2）

依赖安装:
    pip install markdown pyyaml playwright
    playwright install chromium
"""

import argparse
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import markdown
    import yaml
    from playwright.async_api import async_playwright
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: pip install markdown pyyaml playwright && playwright install chromium")
    sys.exit(1)


# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.parent
ASSETS_DIR = SCRIPT_DIR / "assets"
THEMES_DIR = ASSETS_DIR / "themes"

# 默认卡片尺寸配置 (3:4 比例)
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1440
MAX_HEIGHT = 4320  # dynamic 模式最大高度

# 可用主题列表
AVAILABLE_THEMES = [
    'default',
    'playful-geometric',
    'neo-brutalism',
    'botanical',
    'professional',
    'retro',
    'terminal',
    'sketch',
    'xiaohongshu',
    'magazine',
    'glassmorphism',
    'gradient-pop',
    'dark-elegant'
]

# 分页模式
PAGING_MODES = ['separator', 'auto-fit', 'auto-split', 'dynamic']

# 封面布局样式
COVER_STYLES = ['classic', 'centered', 'full', 'split', 'poster']

# ============================================================
# 主题色彩配置
# ============================================================

# 主题封面背景渐变（外层容器）
THEME_COVER_BG = {
    'default':            'linear-gradient(180deg, #f3f3f3 0%, #f9f9f9 100%)',
    'playful-geometric':  'linear-gradient(180deg, #8B5CF6 0%, #F472B6 100%)',
    'neo-brutalism':      'linear-gradient(180deg, #FF4757 0%, #FECA57 100%)',
    'botanical':          'linear-gradient(180deg, #4A7C59 0%, #8FBC8F 100%)',
    'professional':       'linear-gradient(180deg, #2563EB 0%, #3B82F6 100%)',
    'retro':              'linear-gradient(180deg, #D35400 0%, #F39C12 100%)',
    'terminal':           'linear-gradient(180deg, #0D1117 0%, #21262D 100%)',
    'sketch':             'linear-gradient(180deg, #555555 0%, #999999 100%)',
    'xiaohongshu':        'linear-gradient(135deg, #FF2442 0%, #FF6B81 100%)',
    'magazine':           'linear-gradient(180deg, #1a1a1a 0%, #333333 100%)',
    'glassmorphism':      'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
    'gradient-pop':       'linear-gradient(135deg, #f093fb 0%, #f5576c 50%, #ffd26f 100%)',
    'dark-elegant':       'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
}

# 主题卡片背景渐变（卡片外层容器）
THEME_CARD_BG = {
    'default':            'linear-gradient(180deg, #f3f3f3 0%, #f9f9f9 100%)',
    'playful-geometric':  'linear-gradient(135deg, #8B5CF6 0%, #F472B6 100%)',
    'neo-brutalism':      'linear-gradient(135deg, #FF4757 0%, #FECA57 100%)',
    'botanical':          'linear-gradient(135deg, #4A7C59 0%, #8FBC8F 100%)',
    'professional':       'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
    'retro':              'linear-gradient(135deg, #D35400 0%, #F39C12 100%)',
    'terminal':           'linear-gradient(135deg, #0D1117 0%, #161B22 100%)',
    'sketch':             'linear-gradient(135deg, #555555 0%, #888888 100%)',
    'xiaohongshu':        'linear-gradient(135deg, #FF2442 0%, #FF6B81 100%)',
    'magazine':           'linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%)',
    'glassmorphism':      'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
    'gradient-pop':       'linear-gradient(135deg, #f093fb 0%, #f5576c 50%, #ffd26f 100%)',
    'dark-elegant':       'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
}

# 封面标题文字渐变色
THEME_TITLE_GRADIENT = {
    'default':            'linear-gradient(180deg, #111827 0%, #4B5563 100%)',
    'playful-geometric':  'linear-gradient(180deg, #7C3AED 0%, #F472B6 100%)',
    'neo-brutalism':      'linear-gradient(180deg, #000000 0%, #FF4757 100%)',
    'botanical':          'linear-gradient(180deg, #1F2937 0%, #4A7C59 100%)',
    'professional':       'linear-gradient(180deg, #1E3A8A 0%, #2563EB 100%)',
    'retro':              'linear-gradient(180deg, #8B4513 0%, #D35400 100%)',
    'terminal':           'linear-gradient(180deg, #39D353 0%, #58A6FF 100%)',
    'sketch':             'linear-gradient(180deg, #111827 0%, #6B7280 100%)',
    'xiaohongshu':        'linear-gradient(180deg, #FF2442 0%, #FF6B81 100%)',
    'magazine':           'linear-gradient(180deg, #000000 0%, #333333 100%)',
    'glassmorphism':      'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'gradient-pop':       'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'dark-elegant':       'linear-gradient(180deg, #D4AF37 0%, #F5E6A3 100%)',
}

# 主题强调色
THEME_ACCENT = {
    'default':            '#6366f1',
    'playful-geometric':  '#8B5CF6',
    'neo-brutalism':      '#FF4757',
    'botanical':          '#4A7C59',
    'professional':       '#2563EB',
    'retro':              '#D35400',
    'terminal':           '#39D353',
    'sketch':             '#666666',
    'xiaohongshu':        '#FF2442',
    'magazine':           '#C41E3A',
    'glassmorphism':      '#667eea',
    'gradient-pop':       '#f5576c',
    'dark-elegant':       '#D4AF37',
}

# 封面内卡片背景色
THEME_INNER_BG = {
    'default':            '#F3F3F3',
    'playful-geometric':  '#F3F3F3',
    'neo-brutalism':      '#F3F3F3',
    'botanical':          '#F3F3F3',
    'professional':       '#FFFFFF',
    'retro':              '#FDF6E3',
    'terminal':           '#161B22',
    'sketch':             '#FFFEF9',
    'xiaohongshu':        '#FFF5F5',
    'magazine':           '#FFFFFF',
    'glassmorphism':      'rgba(255,255,255,0.85)',
    'gradient-pop':       '#FFFFFF',
    'dark-elegant':       '#1a1a2e',
}

# 封面副标题颜色
THEME_SUBTITLE_COLOR = {
    'default':            '#555555',
    'playful-geometric':  '#666666',
    'neo-brutalism':      '#333333',
    'botanical':          '#555555',
    'professional':       '#555555',
    'retro':              '#8B4513',
    'terminal':           '#8B949E',
    'sketch':             '#666666',
    'xiaohongshu':        '#999999',
    'magazine':           '#666666',
    'glassmorphism':      '#666666',
    'gradient-pop':       '#666666',
    'dark-elegant':       'rgba(212,175,55,0.6)',
}


def parse_markdown_file(file_path: str) -> dict:
    """解析 Markdown 文件，提取 YAML 头部和正文内容"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析 YAML 头部
    yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    yaml_match = re.match(yaml_pattern, content, re.DOTALL)

    metadata = {}
    body = content

    if yaml_match:
        try:
            metadata = yaml.safe_load(yaml_match.group(1)) or {}
        except yaml.YAMLError:
            metadata = {}
        body = content[yaml_match.end():]

    return {
        'metadata': metadata,
        'body': body.strip()
    }


def split_content_by_separator(body: str) -> List[str]:
    """按照 --- 分隔符拆分正文为多张卡片内容"""
    parts = re.split(r'\n---+\n', body)
    return [part.strip() for part in parts if part.strip()]


def convert_markdown_to_html(md_content: str) -> str:
    """将 Markdown 转换为 HTML"""
    # 处理 tags（以 # 开头的标签）
    tags_pattern = r'((?:#[\w\u4e00-\u9fa5]+\s*)+)$'
    tags_match = re.search(tags_pattern, md_content, re.MULTILINE)
    tags_html = ""

    if tags_match:
        tags_str = tags_match.group(1)
        md_content = md_content[:tags_match.start()].strip()
        tags = re.findall(r'#([\w\u4e00-\u9fa5]+)', tags_str)
        if tags:
            tags_html = '<div class="tags-container">'
            for tag in tags:
                tags_html += f'<span class="tag">#{tag}</span>'
            tags_html += '</div>'

    # 转换 Markdown 为 HTML
    html = markdown.markdown(
        md_content,
        extensions=['extra', 'codehilite', 'tables', 'nl2br']
    )

    return html + tags_html


def load_theme_css(theme: str) -> str:
    """加载主题 CSS 样式"""
    theme_file = THEMES_DIR / f"{theme}.css"
    if theme_file.exists():
        with open(theme_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # 如果主题不存在，使用默认主题
        default_file = THEMES_DIR / "default.css"
        if default_file.exists():
            with open(default_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""


def _compute_title_size(title: str, width: int, cover_style: str = 'classic') -> int:
    """根据标题长度和封面风格计算标题字号"""
    title_len = len(title)

    if cover_style == 'poster':
        # poster 布局使用超大标题
        if title_len <= 4:
            return int(width * 0.22)
        elif title_len <= 8:
            return int(width * 0.17)
        elif title_len <= 12:
            return int(width * 0.13)
        else:
            return int(width * 0.10)
    elif cover_style == 'split':
        # split 布局右侧空间有限，标题稍小
        if title_len <= 6:
            return int(width * 0.11)
        elif title_len <= 10:
            return int(width * 0.09)
        elif title_len <= 18:
            return int(width * 0.07)
        else:
            return int(width * 0.055)
    else:
        # 标准标题大小
        if title_len <= 6:
            return int(width * 0.14)
        elif title_len <= 10:
            return int(width * 0.12)
        elif title_len <= 18:
            return int(width * 0.09)
        elif title_len <= 30:
            return int(width * 0.07)
        else:
            return int(width * 0.055)


def _cover_html_head(width: int, height: int) -> str:
    """封面共用 HTML 头部"""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width={width}, height={height}">
    <title>小红书封面</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans SC', 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            width: {width}px;
            height: {height}px;
            overflow: hidden;
        }}
    </style>
</head>
<body>'''


def _cover_classic(emoji, title, subtitle, title_size, bg, title_bg, accent, inner_bg, sub_color, w, h):
    """经典布局 - 增强版：内卡片 + 装饰元素 + 强调线"""
    return f'''
    <div style="width:{w}px;height:{h}px;background:{bg};position:relative;overflow:hidden;">
        <!-- 装饰元素 -->
        <div style="position:absolute;top:55px;right:40px;width:100px;height:100px;border:3px solid rgba(0,0,0,0.04);border-radius:50%;"></div>
        <div style="position:absolute;bottom:90px;left:30px;width:55px;height:55px;background:rgba(0,0,0,0.025);border-radius:50%;"></div>
        <div style="position:absolute;top:42%;right:18px;width:30px;height:30px;background:rgba(0,0,0,0.02);border-radius:50%;"></div>
        <!-- 内卡片 -->
        <div style="position:absolute;width:{int(w*0.88)}px;height:{int(h*0.91)}px;left:{int(w*0.06)}px;top:{int(h*0.045)}px;background:{inner_bg};border-radius:28px;display:flex;flex-direction:column;padding:{int(w*0.074)}px {int(w*0.079)}px;box-shadow:0 2px 20px rgba(0,0,0,0.04);">
            <div style="font-size:{int(w*0.167)}px;line-height:1.2;margin-bottom:{int(h*0.03)}px;">{emoji}</div>
            <div style="font-weight:900;font-size:{title_size}px;line-height:1.35;background:{title_bg};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;flex:1;display:flex;align-items:flex-start;word-break:normal;overflow-wrap:break-word;">{title}</div>
            <div style="width:80px;height:4px;background:{accent};border-radius:2px;margin-bottom:25px;opacity:0.8;"></div>
            <div style="font-weight:350;font-size:{int(w*0.067)}px;line-height:1.4;color:{sub_color};">{subtitle}</div>
        </div>
    </div>'''


def _cover_centered(emoji, title, subtitle, title_size, bg, title_bg, accent, inner_bg, sub_color, w, h):
    """居中布局 - 居中排列 + 装饰圆环 + 分隔线"""
    return f'''
    <div style="width:{w}px;height:{h}px;background:{bg};position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;">
        <!-- 装饰圆环 -->
        <div style="position:absolute;width:520px;height:520px;border:2px dashed rgba(255,255,255,0.1);border-radius:50%;"></div>
        <div style="position:absolute;width:780px;height:780px;border:1px solid rgba(255,255,255,0.05);border-radius:50%;"></div>
        <div style="position:absolute;top:80px;left:80px;width:20px;height:20px;background:rgba(255,255,255,0.08);border-radius:50%;"></div>
        <div style="position:absolute;bottom:120px;right:100px;width:14px;height:14px;background:rgba(255,255,255,0.06);border-radius:50%;"></div>
        <!-- 内容卡片 -->
        <div style="width:{int(w*0.88)}px;height:{int(h*0.88)}px;background:{inner_bg};border-radius:30px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:{int(w*0.074)}px;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.08);">
            <!-- Emoji + 装饰环 -->
            <div style="position:relative;margin-bottom:{int(h*0.035)}px;">
                <div style="width:240px;height:240px;border:3px solid {accent};border-radius:50%;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);opacity:0.15;"></div>
                <div style="font-size:{int(w*0.14)}px;line-height:1;position:relative;">{emoji}</div>
            </div>
            <!-- 标题 -->
            <div style="font-weight:900;font-size:{title_size}px;line-height:1.3;background:{title_bg};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:{int(h*0.022)}px;word-break:normal;overflow-wrap:break-word;max-width:90%;">{title}</div>
            <!-- 分隔线 -->
            <div style="width:60px;height:3px;background:{accent};border-radius:2px;margin-bottom:{int(h*0.022)}px;opacity:0.6;"></div>
            <!-- 副标题 -->
            <div style="font-weight:400;font-size:{int(w*0.048)}px;line-height:1.5;color:{sub_color};max-width:85%;">{subtitle}</div>
        </div>
    </div>'''


def _cover_full(emoji, title, subtitle, title_size, bg, title_bg, accent, inner_bg, sub_color, w, h):
    """全出血布局 - 无内卡片，全渐变背景，大胆白色文字"""
    return f'''
    <div style="width:{w}px;height:{h}px;background:{bg};position:relative;overflow:hidden;">
        <!-- 装饰几何形状 -->
        <div style="position:absolute;width:450px;height:450px;border-radius:50%;background:rgba(255,255,255,0.05);top:-120px;right:-100px;"></div>
        <div style="position:absolute;width:350px;height:350px;border-radius:50%;background:rgba(255,255,255,0.03);bottom:-80px;left:-80px;"></div>
        <div style="position:absolute;width:200px;height:200px;border-radius:50%;border:2px solid rgba(255,255,255,0.06);top:38%;left:10%;"></div>
        <div style="position:absolute;width:80px;height:80px;border-radius:50%;background:rgba(255,255,255,0.04);top:18%;right:22%;"></div>
        <div style="position:absolute;width:120px;height:120px;border-radius:50%;border:1.5px solid rgba(255,255,255,0.04);bottom:25%;right:8%;"></div>
        <!-- 底部渐变遮罩增加层次感 -->
        <div style="position:absolute;bottom:0;left:0;right:0;height:40%;background:linear-gradient(to top,rgba(0,0,0,0.15),transparent);"></div>
        <!-- 内容 -->
        <div style="position:absolute;inset:0;padding:{int(h*0.08)}px {int(w*0.08)}px;display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:{int(w*0.15)}px;line-height:1;margin-bottom:{int(h*0.035)}px;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.12));">{emoji}</div>
            <div style="font-weight:900;font-size:{title_size}px;line-height:1.25;color:white;text-shadow:0 2px 20px rgba(0,0,0,0.12);margin-bottom:{int(h*0.02)}px;word-break:normal;overflow-wrap:break-word;">{title}</div>
            <div style="width:80px;height:4px;background:rgba(255,255,255,0.5);border-radius:2px;margin-bottom:{int(h*0.02)}px;"></div>
            <div style="font-weight:400;font-size:{int(w*0.05)}px;line-height:1.5;color:rgba(255,255,255,0.8);text-shadow:0 1px 8px rgba(0,0,0,0.1);">{subtitle}</div>
        </div>
    </div>'''


def _cover_split(emoji, title, subtitle, title_size, bg, title_bg, accent, inner_bg, sub_color, w, h):
    """分割布局 - 左侧色块 + 右侧内容"""
    left_w = int(w * 0.38)
    right_w = w - left_w
    return f'''
    <div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;display:flex;">
        <!-- 左侧色块 -->
        <div style="width:{left_w}px;height:100%;background:{bg};display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;">
            <!-- 装饰 -->
            <div style="position:absolute;width:180px;height:180px;border-radius:50%;border:2px solid rgba(255,255,255,0.08);top:12%;left:8%;"></div>
            <div style="position:absolute;width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,0.04);bottom:18%;right:12%;"></div>
            <div style="position:absolute;width:50px;height:50px;border-radius:50%;background:rgba(255,255,255,0.06);top:60%;left:20%;"></div>
            <!-- Emoji -->
            <div style="font-size:{int(w*0.17)}px;line-height:1;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.1));position:relative;">{emoji}</div>
        </div>
        <!-- 右侧内容 -->
        <div style="width:{right_w}px;height:100%;background:{inner_bg};display:flex;flex-direction:column;justify-content:center;padding:{int(w*0.06)}px {int(w*0.055)}px;">
            <div style="font-weight:900;font-size:{title_size}px;line-height:1.3;background:{title_bg};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:{int(h*0.025)}px;word-break:normal;overflow-wrap:break-word;">{title}</div>
            <div style="width:55px;height:3px;background:{accent};border-radius:2px;margin-bottom:{int(h*0.02)}px;opacity:0.7;"></div>
            <div style="font-weight:350;font-size:{int(w*0.044)}px;line-height:1.5;color:{sub_color};">{subtitle}</div>
        </div>
    </div>'''


def _cover_poster(emoji, title, subtitle, title_size, bg, title_bg, accent, inner_bg, sub_color, w, h):
    """海报布局 - 超大标题占主体空间，强视觉冲击"""
    return f'''
    <div style="width:{w}px;height:{h}px;background:{bg};position:relative;overflow:hidden;">
        <!-- 装饰线条 -->
        <div style="position:absolute;top:0;left:{int(w*0.075)}px;width:2px;height:100%;background:rgba(255,255,255,0.06);"></div>
        <div style="position:absolute;top:0;right:{int(w*0.12)}px;width:1px;height:100%;background:rgba(255,255,255,0.03);"></div>
        <!-- 内卡片 -->
        <div style="position:absolute;width:{int(w*0.88)}px;height:{int(h*0.91)}px;left:{int(w*0.06)}px;top:{int(h*0.045)}px;background:{inner_bg};border-radius:28px;display:flex;flex-direction:column;padding:{int(w*0.074)}px;box-shadow:0 2px 20px rgba(0,0,0,0.04);">
            <!-- 小 Emoji -->
            <div style="font-size:{int(w*0.07)}px;line-height:1;margin-bottom:{int(h*0.01)}px;">{emoji}</div>
            <!-- 超大标题 -->
            <div style="font-weight:900;font-size:{title_size}px;line-height:1.15;background:{title_bg};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;flex:1;display:flex;align-items:center;letter-spacing:-3px;word-break:normal;overflow-wrap:break-word;">{title}</div>
            <!-- 底部：强调线 + 副标题 -->
            <div style="display:flex;align-items:center;gap:20px;margin-top:auto;">
                <div style="width:50px;height:3px;background:{accent};border-radius:2px;flex-shrink:0;opacity:0.7;"></div>
                <div style="font-weight:400;font-size:{int(w*0.042)}px;color:{sub_color};">{subtitle}</div>
            </div>
        </div>
    </div>'''


def generate_cover_html(metadata: dict, theme: str, width: int, height: int,
                        cover_style: str = 'classic') -> str:
    """生成封面 HTML，支持多种封面布局风格"""
    emoji = metadata.get('emoji', '📝')
    title = metadata.get('title', '标题')
    subtitle = metadata.get('subtitle', '')

    title_size = _compute_title_size(title, width, cover_style)
    bg = THEME_COVER_BG.get(theme, THEME_COVER_BG['default'])
    title_bg = THEME_TITLE_GRADIENT.get(theme, THEME_TITLE_GRADIENT['default'])
    accent = THEME_ACCENT.get(theme, THEME_ACCENT['default'])
    inner_bg = THEME_INNER_BG.get(theme, THEME_INNER_BG['default'])
    sub_color = THEME_SUBTITLE_COLOR.get(theme, THEME_SUBTITLE_COLOR['default'])

    # full 布局：浅色主题需要更鲜艳的背景才能衬托白色文字
    if cover_style == 'full' and theme in ('default', 'sketch'):
        bg = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'

    html_head = _cover_html_head(width, height)
    html_foot = '\n</body>\n</html>'

    cover_builders = {
        'classic':  _cover_classic,
        'centered': _cover_centered,
        'full':     _cover_full,
        'split':    _cover_split,
        'poster':   _cover_poster,
    }
    builder = cover_builders.get(cover_style, _cover_classic)
    body = builder(emoji, title, subtitle, title_size, bg, title_bg, accent, inner_bg, sub_color, width, height)

    return html_head + body + html_foot


def generate_card_html(content: str, theme: str, page_number: int = 1,
                       total_pages: int = 1, width: int = DEFAULT_WIDTH,
                       height: int = DEFAULT_HEIGHT, mode: str = 'separator') -> str:
    """生成正文卡片 HTML"""

    html_content = convert_markdown_to_html(content)
    theme_css = load_theme_css(theme)

    page_text = f"{page_number}/{total_pages}" if total_pages > 1 else ""

    bg = THEME_CARD_BG.get(theme, THEME_CARD_BG['default'])

    # 页码颜色：深色主题用亮色页码
    page_color = 'rgba(255, 255, 255, 0.8)'
    if theme in ('default', 'sketch'):
        page_color = 'rgba(0, 0, 0, 0.25)'

    # 根据模式设置不同的容器样式
    if mode == 'auto-fit':
        container_style = f'''
            width: {width}px;
            height: {height}px;
            background: {bg};
            position: relative;
            padding: 50px;
            overflow: hidden;
        '''
        inner_style = f'''
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 60px;
            height: calc({height}px - 100px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        '''
        content_style = '''
            flex: 1;
            overflow: hidden;
        '''
    elif mode == 'dynamic':
        container_style = f'''
            width: {width}px;
            min-height: {height}px;
            background: {bg};
            position: relative;
            padding: 50px;
        '''
        inner_style = '''
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 60px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        '''
        content_style = ''
    else:  # separator 和 auto-split
        container_style = f'''
            width: {width}px;
            min-height: {height}px;
            background: {bg};
            position: relative;
            padding: 50px;
            overflow: hidden;
        '''
        inner_style = f'''
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 60px;
            min-height: calc({height}px - 100px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        '''
        content_style = ''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width={width}">
    <title>小红书卡片</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Noto Sans SC', 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            width: {width}px;
            overflow: hidden;
            background: transparent;
        }}

        .card-container {{
            {container_style}
        }}

        .card-inner {{
            {inner_style}
        }}

        .card-content {{
            line-height: 1.7;
            {content_style}
        }}

        /* auto-fit 用：对整个内容块做 transform 缩放 */
        .card-content-scale {{
            transform-origin: top left;
            will-change: transform;
        }}

        {theme_css}

        .page-number {{
            position: absolute;
            bottom: 80px;
            right: 80px;
            font-size: 36px;
            color: {page_color};
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="card-container">
        <div class="card-inner">
            <div class="card-content">
                <div class="card-content-scale">{html_content}</div>
            </div>
        </div>
        <div class="page-number">{page_text}</div>
    </div>
</body>
</html>'''
    return html


async def render_html_to_image(html_content: str, output_path: str,
                               width: int = DEFAULT_WIDTH,
                               height: int = DEFAULT_HEIGHT,
                               mode: str = 'separator',
                               max_height: int = MAX_HEIGHT,
                               dpr: int = 2):
    """使用 Playwright 将 HTML 渲染为图片"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # 设置视口大小
        viewport_height = height if mode != 'dynamic' else max_height
        page = await browser.new_page(
            viewport={'width': width, 'height': viewport_height},
            device_scale_factor=dpr
        )

        # 创建临时 HTML 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html_path = f.name

        try:
            await page.goto(f'file://{temp_html_path}')
            await page.wait_for_load_state('networkidle')

            # 等待字体加载
            await page.wait_for_timeout(500)

            if mode == 'auto-fit':
                # 自动缩放模式：对整个内容块做 transform 缩放（标题/代码块等固定 px 也会一起缩放）
                await page.evaluate('''() => {
                    const viewportContent = document.querySelector('.card-content');
                    const scaleEl = document.querySelector('.card-content-scale');
                    if (!viewportContent || !scaleEl) return;

                    // 先重置，测量原始尺寸
                    scaleEl.style.transform = 'none';
                    scaleEl.style.width = '';
                    scaleEl.style.height = '';

                    const availableWidth = viewportContent.clientWidth;
                    const availableHeight = viewportContent.clientHeight;

                    // scrollWidth/scrollHeight 反映内容的自然尺寸
                    const contentWidth = Math.max(scaleEl.scrollWidth, scaleEl.getBoundingClientRect().width);
                    const contentHeight = Math.max(scaleEl.scrollHeight, scaleEl.getBoundingClientRect().height);

                    if (!contentWidth || !contentHeight || !availableWidth || !availableHeight) return;

                    // 只缩小不放大，避免"撑太大"
                    const scale = Math.min(1, availableWidth / contentWidth, availableHeight / contentHeight);

                    // 为避免 transform 后布局尺寸不匹配导致裁切，扩大布局盒子
                    scaleEl.style.width = (availableWidth / scale) + 'px';

                    // 顶部对齐更稳；如需居中可计算 offset
                    const offsetX = 0;
                    const offsetY = 0;

                    scaleEl.style.transformOrigin = 'top left';
                    scaleEl.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
                }''')
                await page.wait_for_timeout(100)
                actual_height = height

            elif mode == 'dynamic':
                # 动态高度模式：根据内容调整图片高度
                content_height = await page.evaluate('''() => {
                    const container = document.querySelector('.card-container');
                    return container ? container.scrollHeight : document.body.scrollHeight;
                }''')
                # 确保高度在合理范围内
                actual_height = max(height, min(content_height, max_height))

            else:  # separator 和 auto-split
                # 获取实际内容高度
                content_height = await page.evaluate('''() => {
                    const container = document.querySelector('.card-container');
                    return container ? container.scrollHeight : document.body.scrollHeight;
                }''')
                actual_height = max(height, content_height)

            # 截图
            await page.screenshot(
                path=output_path,
                clip={'x': 0, 'y': 0, 'width': width, 'height': actual_height},
                type='png'
            )

            print(f"  ✅ 已生成: {output_path} ({width}x{actual_height})")
            return actual_height

        finally:
            os.unlink(temp_html_path)
            await browser.close()


async def auto_split_content(body: str, theme: str, width: int, height: int,
                             dpr: int = 2) -> List[str]:
    """自动切分内容：根据渲染后的高度自动分页"""

    # 将内容按段落分割
    paragraphs = re.split(r'\n\n+', body)

    cards = []
    current_content = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={'width': width, 'height': height * 2},
            device_scale_factor=dpr
        )

        try:
            for para in paragraphs:
                # 尝试将当前段落加入
                test_content = current_content + [para]
                test_md = '\n\n'.join(test_content)

                html = generate_card_html(test_md, theme, 1, 1, width, height, 'auto-split')

                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                    f.write(html)
                    temp_path = f.name

                await page.goto(f'file://{temp_path}')
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(200)

                content_height = await page.evaluate('''() => {
                    const content = document.querySelector('.card-content');
                    return content ? content.scrollHeight : 0;
                }''')

                os.unlink(temp_path)

                # 内容区域的可用高度（去除 padding 等）
                available_height = height - 220  # 50*2 padding + 60*2 inner padding

                if content_height > available_height and current_content:
                    # 当前卡片已满，保存并开始新卡片
                    cards.append('\n\n'.join(current_content))
                    current_content = [para]
                else:
                    current_content = test_content

            # 保存最后一张卡片
            if current_content:
                cards.append('\n\n'.join(current_content))

        finally:
            await browser.close()

    return cards


async def render_markdown_to_cards(md_file: str, output_dir: str,
                                   theme: str = 'default',
                                   mode: str = 'separator',
                                   cover_style: str = 'classic',
                                   width: int = DEFAULT_WIDTH,
                                   height: int = DEFAULT_HEIGHT,
                                   max_height: int = MAX_HEIGHT,
                                   dpr: int = 2):
    """主渲染函数：将 Markdown 文件渲染为多张卡片图片"""
    print(f"\n🎨 开始渲染: {md_file}")
    print(f"  📐 主题: {theme}")
    print(f"  📷 封面: {cover_style}")
    print(f"  📏 模式: {mode}")
    print(f"  📐 尺寸: {width}x{height}")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 解析 Markdown 文件
    data = parse_markdown_file(md_file)
    metadata = data['metadata']
    body = data['body']

    # 根据模式处理内容分割
    if mode == 'auto-split':
        print("  ⏳ 自动分析内容并切分...")
        card_contents = await auto_split_content(body, theme, width, height, dpr)
    else:
        card_contents = split_content_by_separator(body)

    total_cards = len(card_contents)
    print(f"  📄 检测到 {total_cards} 张正文卡片")

    # 生成封面
    if metadata.get('emoji') or metadata.get('title'):
        print(f"  📷 生成封面（{cover_style} 布局）...")
        cover_html = generate_cover_html(metadata, theme, width, height, cover_style)
        cover_path = os.path.join(output_dir, 'cover.png')
        await render_html_to_image(cover_html, cover_path, width, height, 'separator', max_height, dpr)

    # 生成正文卡片
    for i, content in enumerate(card_contents, 1):
        print(f"  📷 生成卡片 {i}/{total_cards}...")
        card_html = generate_card_html(content, theme, i, total_cards, width, height, mode)
        card_path = os.path.join(output_dir, f'card_{i}.png')
        await render_html_to_image(card_html, card_path, width, height, mode, max_height, dpr)

    print(f"\n✨ 渲染完成！图片已保存到: {output_dir}")
    return total_cards


def main():
    parser = argparse.ArgumentParser(
        description='将 Markdown 文件渲染为小红书风格的图片卡片（支持多种样式和分页模式）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
可用主题:
  default           - 默认简约风格
  playful-geometric - 活泼几何风格（Memphis 设计）
  neo-brutalism     - 新粗野主义风格
  botanical         - 植物园自然风格
  professional      - 专业商务风格
  retro             - 复古怀旧风格
  terminal          - 终端/命令行风格
  sketch            - 手绘素描风格
  xiaohongshu       - 小红书原生风格（珊瑚红 + 暖粉）
  magazine          - 杂志编辑风格（黑白 + 红色点缀）
  glassmorphism     - 毛玻璃风格（现代半透明）
  gradient-pop      - 渐变流行风格（鲜艳渐变色）
  dark-elegant      - 暗夜优雅风格（深色 + 金色点缀）

封面布局:
  classic   - 经典布局：内卡片 + 装饰元素（默认）
  centered  - 居中布局：内容居中 + 装饰圆环
  full      - 全出血布局：无内卡片，渐变背景上直接白色文字
  split     - 分割布局：左侧色块 + 右侧内容
  poster    - 海报布局：超大标题，强视觉冲击

分页模式:
  separator   - 按 --- 分隔符手动分页（默认）
  auto-fit    - 自动缩放文字以填满固定尺寸
  auto-split  - 根据内容高度自动切分
  dynamic     - 根据内容动态调整图片高度
'''
    )
    parser.add_argument(
        'markdown_file',
        help='Markdown 文件路径'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default=os.getcwd(),
        help='输出目录（默认为当前工作目录）'
    )
    parser.add_argument(
        '--theme', '-t',
        choices=AVAILABLE_THEMES,
        default='default',
        help='排版主题（默认: default）'
    )
    parser.add_argument(
        '--cover', '-c',
        choices=COVER_STYLES,
        default='classic',
        help='封面布局风格（默认: classic）'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=PAGING_MODES,
        default='separator',
        help='分页模式（默认: separator）'
    )
    parser.add_argument(
        '--width', '-w',
        type=int,
        default=DEFAULT_WIDTH,
        help=f'图片宽度（默认: {DEFAULT_WIDTH}）'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=DEFAULT_HEIGHT,
        help=f'图片高度（默认: {DEFAULT_HEIGHT}）'
    )
    parser.add_argument(
        '--max-height',
        type=int,
        default=MAX_HEIGHT,
        help=f'dynamic 模式下的最大高度（默认: {MAX_HEIGHT}）'
    )
    parser.add_argument(
        '--dpr',
        type=int,
        default=2,
        help='设备像素比（默认: 2）'
    )

    args = parser.parse_args()

    if not os.path.exists(args.markdown_file):
        print(f"❌ 错误: 文件不存在 - {args.markdown_file}")
        sys.exit(1)

    asyncio.run(render_markdown_to_cards(
        args.markdown_file,
        args.output_dir,
        theme=args.theme,
        mode=args.mode,
        cover_style=args.cover,
        width=args.width,
        height=args.height,
        max_height=args.max_height,
        dpr=args.dpr
    ))


if __name__ == '__main__':
    main()
