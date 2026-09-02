"""编辑共享层：tag/rating 变更 → DB 重渲染 → edit 目标消息 → 刷新索引。

verify 双向同步的唯一入口（Telegram 命令与 Web API 均走这里）。
"""

from __future__ import annotations

from types import SimpleNamespace

from app.database.migrate import apply_migrations, open_db
from app.processor.adapter import build_incoming
from app.processor.edit import apply_message_edit, extract_edited_body
from app.processor.recorder import record_message


def _setup(tmp_path, chat_id=-1001):
    conn = open_db(tmp_path / "e.sqlite")
    apply_migrations(conn)
    msg = _incoming(chat_id=chat_id, tags_text="正文")
    mid = record_message(
        conn, build_incoming(msg, chat_id, None), source_tags=[], preserve_original=False
    )
    # 模拟已归档：设目标 + 重渲染
    conn.execute(
        "UPDATE messages SET status='archived', target_chat_id=-1005, "
        "target_message_id=99, rendered_text='正文' WHERE id=?",
        (mid,),
    )
    conn.commit()
    return conn, mid


def _incoming(chat_id=-1001, mid=7, tags_text="正文"):
    return SimpleNamespace(id=mid, message=tags_text, media=None, grouped_id=None)


class _FakeClient:
    """记录 edit_message 调用的假客户端。"""

    def __init__(self):
        self.edits = []

    async def edit_message(self, chat_id, message_id, text):
        self.edits.append((chat_id, message_id, text))


def test_apply_rating_edits_target(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid, rating=4))
    row = conn.execute("SELECT rating, rendered_text FROM messages WHERE id=?", (mid,)).fetchone()
    assert row["rating"] == 4
    assert client.edits == [(-1005, 99, row["rendered_text"])]


def test_apply_add_tags_and_indexer(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    calls = {"n": 0}

    class Indexer:
        def schedule(self):
            calls["n"] += 1

    assert asyncio_run(
        apply_message_edit(client, conn, mid, add_tags=["游戏", "MOD"], indexer=Indexer())
    )
    tags = {
        r["name"] for r in conn.execute(
            "SELECT t.name FROM message_tags mt JOIN tags t ON t.id=mt.tag_id "
            "WHERE mt.message_id=?", (mid,)
        )
    }
    assert tags == {"游戏", "MOD"}
    assert calls["n"] == 1
    assert len(client.edits) == 1


def test_apply_remove_tags(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    asyncio_run(
        apply_message_edit(client, conn, mid, add_tags=["保留", "删除"], indexer=None)
    )
    client.edits.clear()
    assert asyncio_run(
        apply_message_edit(client, conn, mid, remove_tag_names=["删除"])
    )
    tags = {
        r["name"] for r in conn.execute(
            "SELECT t.name FROM message_tags mt JOIN tags t ON t.id=mt.tag_id "
            "WHERE mt.message_id=?", (mid,)
        )
    }
    assert tags == {"保留"}


def test_apply_nonexistent_message_returns_false(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, 99999, rating=3)) is False
    assert client.edits == []


def test_apply_no_action_returns_false(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid)) is False
    assert client.edits == []



def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def _setup_target(tmp_path):
    conn, mid = _setup(tmp_path)
    conn.execute(
        "INSERT INTO message_targets "
        "(id, message_id, target_chat_id, target_message_id, status, original_text, "
        "original_html, rendered_text, rating) "
        "VALUES (1, ?, -1005, 99, 'archived', '正文', '<b>正文</b>', '<b>正文</b>', 0)",
        (mid,),
    )
    conn.commit()
    return conn, mid


def test_target_rating_preserves_existing_html_body(tmp_path):
    conn, mid = _setup_target(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid, target_id=1, rating=4))
    target = conn.execute(
        "SELECT original_text, original_html, rendered_text FROM message_targets WHERE id=1"
    ).fetchone()
    assert target["original_text"] == "正文"
    assert target["original_html"] == "<b>正文</b>"
    assert "<b>正文</b>" in target["rendered_text"]
    assert "<b>正文</b>" in client.edits[0][2]


def test_apply_message_not_modified_treated_as_success(tmp_path):
    """重复添加已有 Tag 等场景 Telegram 返回 MessageNotModified，不应中断同步。"""
    from telethon.errors import MessageNotModifiedError

    class NotModifiedClient:
        async def edit_message(self, *args, **kwargs):
            raise MessageNotModifiedError(None)

    conn, mid = _setup(tmp_path)
    assert asyncio_run(apply_message_edit(NotModifiedClient(), conn, mid, rating=4))
    row = conn.execute("SELECT rating FROM messages WHERE id=?", (mid,)).fetchone()
    assert row["rating"] == 4


def _setup_with_copies(tmp_path):
    """父表 + 两条归档副本，用于数据分叉回归。"""
    conn, mid = _setup(tmp_path)
    for target_id, chat_id, tg_mid in ((1, -1005, 99), (2, -1006, 200)):
        conn.execute(
            "INSERT INTO message_targets "
            "(id, message_id, target_chat_id, target_message_id, status, original_text, "
            "original_html, rendered_text, rating) "
            "VALUES (?, ?, ?, ?, 'archived', '正文', '', '正文', 0)",
            (target_id, mid, chat_id, tg_mid),
        )
    conn.commit()
    return conn, mid


def test_source_level_edit_updates_parent_and_all_copies(tmp_path):
    """E3 回归：源级编辑必须父表+副本双写，不再数据分叉。"""
    conn, mid = _setup_with_copies(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid, rating=4))
    parent = conn.execute("SELECT rating FROM messages WHERE id=?", (mid,)).fetchone()
    assert parent["rating"] == 4
    ratings = {
        row["target_chat_id"]: row["rating"]
        for row in conn.execute(
            "SELECT target_chat_id, rating FROM message_targets WHERE message_id=?", (mid,)
        )
    }
    assert ratings == {-1005: 4, -1006: 4}
    assert {(chat, mid_) for chat, mid_, _ in client.edits} == {(-1005, 99), (-1006, 200)}


def test_source_level_tag_add_mirrors_to_copies(tmp_path):
    """E3 回归：源级加 tag 写父表 message_tags 并镜像到每条副本 target_tags。"""
    conn, mid = _setup_with_copies(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid, add_tags=["游戏"]))
    parent_tags = {
        r["name"] for r in conn.execute(
            "SELECT t.name FROM message_tags mt JOIN tags t ON t.id=mt.tag_id "
            "WHERE mt.message_id=?", (mid,)
        )
    }
    assert parent_tags == {"游戏"}
    copy_tags = {
        row["target_chat_id"]: {r["name"] for r in conn.execute(
            "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
            "WHERE tt.target_id=?", (row["id"],)
        )}
        for row in conn.execute(
            "SELECT id, target_chat_id FROM message_targets WHERE message_id=?", (mid,)
        )
    }
    assert copy_tags == {-1005: {"游戏"}, -1006: {"游戏"}}
    assert len(client.edits) == 2


def test_copy_level_edit_stays_copy_scoped(tmp_path):
    """副本级编辑不传播兄弟副本，也不回写父表标签（独立副本模型不变）。"""
    conn, mid = _setup_with_copies(tmp_path)
    client = _FakeClient()
    assert asyncio_run(
        apply_message_edit(client, conn, mid, target_id=1, add_tags=["画质"])
    )
    sibling_tags = conn.execute(
        "SELECT COUNT(*) AS n FROM target_tags tt "
        "JOIN message_targets mt ON mt.id=tt.target_id WHERE mt.target_chat_id=-1006"
    ).fetchone()["n"]
    parent_tags = conn.execute(
        "SELECT COUNT(*) AS n FROM message_tags WHERE message_id=?", (mid,)
    ).fetchone()["n"]
    assert sibling_tags == 0
    assert parent_tags == 0
    assert {(chat, mid_) for chat, mid_, _ in client.edits} == {(-1005, 99)}


def test_extract_edited_body_strips_full_skeleton():
    text = "推荐指数：⭐⭐⭐\n\n#游戏 #MOD\n\n新正文\n\n来自：\nhttps://t.me/x/1"
    body, body_html = extract_edited_body(
        text, text, tags=["游戏", "MOD"], source_url="https://t.me/x/1"
    )
    assert body == "新正文"
    assert body_html == "新正文"


def test_extract_edited_body_accepts_anchor_url_line():
    """Telegram 编辑后 URL 会被自动加上链接实体，剥离时兼容 <a> 形态。"""
    text = (
        "推荐指数：⭐⭐⭐\n\n#游戏\n\n正文\n\n来自：\n"
        '<a href="https://t.me/x/1">https://t.me/x/1</a>'
    )
    body, _ = extract_edited_body(text, text, tags=["游戏"], source_url="https://t.me/x/1")
    assert body == "正文"


def test_extract_edited_body_without_skeleton():
    body, _ = extract_edited_body("只有正文", "只有正文", tags=[], source_url=None)
    assert body == "只有正文"


def test_extract_edited_body_tags_only_layout():
    text = "#游戏\n\n正文\n\n来自：\nhttps://t.me/x/1"
    body, _ = extract_edited_body(text, text, tags=["游戏"], source_url="https://t.me/x/1")
    assert body == "正文"


def test_extract_edited_body_multiline_body_kept():
    text = "推荐指数：⭐\n\n#游戏\n\n第一段\n\n第二段\n\n来自：\nhttps://t.me/x/1"
    body, _ = extract_edited_body(
        text, text, tags=["游戏"], source_url="https://t.me/x/1"
    )
    assert body == "第一段\n\n第二段"


def test_extract_edited_body_append_after_source():
    """回归：用户习惯在消息末尾（来源块之后）追加内容，来源必须从正文中移除。"""
    text = (
        "推荐指数：⭐⭐⭐\n\n#游戏\n\n原始正文\n\n来自：\nhttps://t.me/x/1\n\n"
        "追加的一句话"
    )
    body, _ = extract_edited_body(text, text, tags=["游戏"], source_url="https://t.me/x/1")
    assert body == "原始正文\n\n追加的一句话"


def test_extract_edited_body_self_heals_stale_skeleton():
    """回归：历史失败轮次留在正文里的来源块（多份）也要全部剥离，逐次自愈。"""
    text = (
        "推荐指数：⭐⭐⭐\n\n#游戏\n\n"
        "原始正文\n\n来自：\nhttps://t.me/x/1\n\n"
        "第一次追加\n\n来自：\nhttps://t.me/x/1\n\n"
        "第二次追加\n\n来自：\nhttps://t.me/x/1"
    )
    body, _ = extract_edited_body(text, text, tags=["游戏"], source_url="https://t.me/x/1")
    assert body == "原始正文\n\n第一次追加\n\n第二次追加"


def test_extract_edited_body_star_count_change_is_still_skeleton():
    """用户在 TG 里加减星号时该行仍被识别为骨架，不混入正文。"""
    text = "推荐指数：⭐⭐⭐⭐⭐\n\n#游戏\n\n正文\n\n来自：\nhttps://t.me/x/1"
    body, _ = extract_edited_body(text, text, tags=["游戏"], source_url="https://t.me/x/1")
    assert body == "正文"
