#!/usr/bin/env python3
"""
小红书评论自动回复脚本

功能：
  1. 获取自己所有笔记的新评论
  2. 结合 AI（Claude API）生成个性化回复
  3. 自动回复评论

使用方法:
    # 查看最近笔记的评论（不回复，仅预览）
    python scripts/reply_comments.py --dry-run

    # 自动回复最近笔记的未回复评论
    python scripts/reply_comments.py

    # 指定回复某篇笔记的评论
    python scripts/reply_comments.py --note-id <note_id>

    # 指定回复规则（不使用AI，使用固定话术）
    python scripts/reply_comments.py --template "谢谢支持！❤️"

    # 使用 AI 生成回复（通过 claude -p 命令，无需 API key）
    python scripts/reply_comments.py --ai

    # 限制处理的笔记数量和每篇最多回复数
    python scripts/reply_comments.py --max-notes 5 --max-replies 10

环境变量（.env）:
    XHS_COOKIE=your_cookie_string_here

依赖安装:
    pip install xhs python-dotenv
"""

import argparse
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from dotenv import load_dotenv
except ImportError:
    print("缺少依赖: python-dotenv")
    print("请运行: pip install python-dotenv")
    sys.exit(1)


# --------------- 工具函数 ---------------

def load_env():
    """从 .env 文件加载环境变量"""
    env_paths = [
        Path.cwd() / '.env',
        Path(__file__).parent.parent / '.env',
        Path(__file__).parent.parent.parent / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            return
    load_dotenv()


def get_cookie() -> str:
    cookie = os.getenv('XHS_COOKIE')
    if not cookie:
        print("❌ 未找到 XHS_COOKIE，请在 .env 中配置")
        sys.exit(1)
    return cookie


def parse_cookie(cookie_string: str) -> Dict[str, str]:
    cookies = {}
    for item in cookie_string.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def init_xhs_client(cookie: str):
    """初始化 xhs 客户端"""
    try:
        from xhs import XhsClient
    except ImportError:
        print("❌ 缺少 xhs 库，请运行: pip install xhs")
        sys.exit(1)

    cookies = parse_cookie(cookie)

    def sign_func(uri, data=None, a1="", web_session="", **kwargs):
        from xhs.help import sign as xhs_sign
        return xhs_sign(uri, data, a1=a1 or cookies.get('a1', ''), b1='')

    return XhsClient(cookie=cookie, sign=sign_func)


# --------------- 已回复记录 ---------------

REPLIED_RECORD_FILE = Path(__file__).parent.parent / '.replied_comments.json'


def load_replied_ids() -> set:
    """加载已回复的评论 ID 集合"""
    if REPLIED_RECORD_FILE.exists():
        try:
            data = json.loads(REPLIED_RECORD_FILE.read_text(encoding='utf-8'))
            return set(data)
        except Exception:
            return set()
    return set()


def save_replied_ids(replied_ids: set):
    """保存已回复的评论 ID"""
    REPLIED_RECORD_FILE.write_text(
        json.dumps(list(replied_ids), ensure_ascii=False),
        encoding='utf-8'
    )


# --------------- AI 回复生成 ---------------

def generate_ai_reply(comment_content: str, note_title: str, user_nickname: str) -> Optional[str]:
    """使用 claude -p 命令生成回复，无需 API key"""
    prompt = (
        f"你是一个小红书博主，正在回复粉丝的评论。请根据以下信息生成一条自然、友好的回复。\n\n"
        f"笔记标题：{note_title}\n"
        f"评论者昵称：{user_nickname}\n"
        f"评论内容：{comment_content}\n\n"
        f"要求：\n"
        f"- 回复简短自然，像真人聊天，不要AI味\n"
        f"- 可以适当用1-2个emoji\n"
        f"- 不超过50字\n"
        f"- 如果评论是负面的或无意义的，回复要得体友善\n"
        f"- 不要用\"亲\"、\"宝\"等过于客服化的称呼\n"
        f"- 只输出回复内容本身，不要任何解释或前缀"
    )

    try:
        result = subprocess.run(
            ['claude', '-p', prompt, '--model', 'haiku'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            stderr = result.stderr.strip()
            if stderr:
                print(f"⚠️ claude 命令错误: {stderr}")
            return None
    except FileNotFoundError:
        print("⚠️ 未找到 claude 命令，请确保已安装 Claude Code CLI")
        return None
    except subprocess.TimeoutExpired:
        print("⚠️ claude 命令超时")
        return None
    except Exception as e:
        print(f"⚠️ AI 生成回复失败: {e}")
        return None


# --------------- 核心逻辑 ---------------

def get_my_notes(client, max_notes: int = 10) -> List[Dict]:
    """获取自己的笔记列表"""
    try:
        user_info = client.get_self_info()
        user_id = user_info.get('user_id')
        if not user_id:
            print("❌ 无法获取用户 ID")
            return []
        print(f"👤 当前用户: {user_info.get('nickname', '未知')}")
    except Exception as e:
        print(f"❌ 获取用户信息失败: {e}")
        return []

    notes = []
    cursor = ""
    while len(notes) < max_notes:
        try:
            result = client.get_user_notes(user_id, cursor=cursor)
            page_notes = result.get('notes', [])
            if not page_notes:
                break
            notes.extend(page_notes)
            if not result.get('has_more', False):
                break
            cursor = result.get('cursor', '')
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ 获取笔记列表出错: {e}")
            break

    return notes[:max_notes]


def get_unreplied_comments(client, note_id: str, my_user_id: str,
                           replied_ids: set) -> List[Dict]:
    """获取某篇笔记下未回复的评论（排除自己的评论）"""
    unreplied = []
    cursor = ""
    try:
        while True:
            result = client.get_note_comments(note_id, cursor=cursor)
            comments = result.get('comments', [])
            if not comments:
                break

            for comment in comments:
                cid = comment.get('id', '')
                commenter_id = comment.get('user_info', {}).get('user_id', '')

                # 跳过自己的评论和已回复的
                if commenter_id == my_user_id:
                    continue
                if cid in replied_ids:
                    continue

                # 检查是否已有自己的子评论（即已手动回复过）
                sub_comments = comment.get('sub_comments', [])
                already_replied = any(
                    sc.get('user_info', {}).get('user_id') == my_user_id
                    for sc in sub_comments
                )
                if already_replied:
                    replied_ids.add(cid)
                    continue

                unreplied.append(comment)

            if not result.get('has_more', False):
                break
            cursor = result.get('cursor', '')
            time.sleep(1)
    except Exception as e:
        print(f"⚠️ 获取评论出错 (note_id={note_id}): {e}")

    return unreplied


def reply_to_comment(client, note_id: str, comment_id: str, content: str) -> bool:
    """回复一条评论"""
    try:
        client.comment_user(note_id, comment_id, content)
        return True
    except Exception as e:
        print(f"  ❌ 回复失败: {e}")
        return False


# --------------- 主流程 ---------------

def main():
    parser = argparse.ArgumentParser(
        description='小红书评论自动回复',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 预览模式（不实际回复）
  python scripts/reply_comments.py --dry-run

  # 使用固定话术回复
  python scripts/reply_comments.py --template "谢谢关注！🙏"

  # AI 智能回复
  python scripts/reply_comments.py --ai

  # 指定笔记 + AI 回复
  python scripts/reply_comments.py --note-id abc123 --ai
'''
    )
    parser.add_argument(
        '--note-id',
        default=None,
        help='指定笔记 ID（不指定则遍历最近笔记）'
    )
    parser.add_argument(
        '--ai',
        action='store_true',
        help='使用 AI 生成个性化回复（通过 claude -p 命令）'
    )
    parser.add_argument(
        '--template',
        default=None,
        help='使用固定话术回复（与 --ai 互斥）'
    )
    parser.add_argument(
        '--max-notes',
        type=int,
        default=10,
        help='最多处理多少篇笔记（默认 10）'
    )
    parser.add_argument(
        '--max-replies',
        type=int,
        default=10,
        help='本次最多回复多少条评论（默认 10）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅预览，不实际回复'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=3.0,
        help='每次回复间隔秒数（默认 3，避免风控）'
    )

    args = parser.parse_args()

    if args.ai and args.template:
        print("❌ --ai 和 --template 不能同时使用")
        sys.exit(1)

    if not args.ai and not args.template and not args.dry_run:
        print("❌ 请指定回复方式: --ai（AI生成）或 --template \"回复内容\"")
        print("   或使用 --dry-run 仅预览评论")
        sys.exit(1)

    # 初始化
    load_env()
    cookie = get_cookie()
    client = init_xhs_client(cookie)
    replied_ids = load_replied_ids()

    # 获取自己的 user_id
    try:
        user_info = client.get_self_info()
        my_user_id = user_info.get('user_id', '')
        print(f"👤 当前用户: {user_info.get('nickname', '未知')}")
    except Exception as e:
        print(f"❌ 获取用户信息失败（Cookie 可能已过期）: {e}")
        sys.exit(1)

    # 获取笔记列表
    if args.note_id:
        notes = [{'note_id': args.note_id, 'display_title': '(指定笔记)'}]
    else:
        print(f"\n📋 获取最近 {args.max_notes} 篇笔记...")
        notes = get_my_notes(client, max_notes=args.max_notes)
        if not notes:
            print("没有找到笔记")
            return
        print(f"  找到 {len(notes)} 篇笔记")

    # 遍历笔记，收集未回复评论
    total_replied = 0
    all_unreplied = []

    for note in notes:
        note_id = note.get('note_id', '')
        title = note.get('display_title', '无标题')
        print(f"\n📝 [{title}]")

        unreplied = get_unreplied_comments(client, note_id, my_user_id, replied_ids)
        if not unreplied:
            print("  ✅ 无新评论需要回复")
            continue

        print(f"  💬 {len(unreplied)} 条新评论")
        for comment in unreplied:
            all_unreplied.append((note_id, title, comment))

    if not all_unreplied:
        print("\n🎉 所有评论都已处理，没有需要回复的新评论")
        save_replied_ids(replied_ids)
        return

    print(f"\n{'='*50}")
    print(f"共 {len(all_unreplied)} 条待回复评论")
    if args.dry_run:
        print("（预览模式，不会实际回复）")
    print(f"{'='*50}")

    # 逐条处理
    for note_id, note_title, comment in all_unreplied:
        if total_replied >= args.max_replies:
            print(f"\n⏸ 已达到最大回复数 {args.max_replies}，停止")
            break

        cid = comment.get('id', '')
        nickname = comment.get('user_info', {}).get('nickname', '匿名')
        content = comment.get('content', '')

        print(f"\n  💬 @{nickname}: {content}")

        # 生成回复内容
        if args.template:
            reply_text = args.template
        elif args.ai:
            reply_text = generate_ai_reply(content, note_title, nickname)
            if not reply_text:
                reply_text = "谢谢你的评论！😊"
        else:
            continue

        print(f"  ↳ 回复: {reply_text}")

        if args.dry_run:
            replied_ids.add(cid)
            total_replied += 1
            continue

        # 实际回复
        if reply_to_comment(client, note_id, cid, reply_text):
            print(f"  ✅ 回复成功")
            replied_ids.add(cid)
            total_replied += 1
            time.sleep(args.interval)
        else:
            print(f"  ⚠️ 跳过此条")

    # 保存记录
    save_replied_ids(replied_ids)
    print(f"\n{'='*50}")
    print(f"✨ 完成！本次共回复 {total_replied} 条评论")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
