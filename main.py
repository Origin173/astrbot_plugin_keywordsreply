from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import re
import os
import json


@register(
    "astrbot_plugin_keywordsreply",
    "Origin173",
    "一个检测到关键词就会回复预定文本的插件",
    "1.0",
    "https://github.com/Origin173/astrbot_plugin_keywordsreply",
)
class krPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}

        self.default_keywords = {}

        self.keywords = self._load_keywords()

        self.enable_regex = self.config.get("enable_regex", False)
        self.case_sensitive = self.config.get("case_sensitive", False)
        self.reply_probability = self.config.get("reply_probability", 1.0)

        logger.info(f"关键词回复插件已加载，共 {len(self.keywords)} 个关键词规则")

    @filter.command_group("kr")
    def kr(self):
        pass

    @kr.command("help")
    async def kr_help(self, event: AstrMessageEvent):
        """关键词回复插件帮助"""
        help_text = """
• /kr list - 查看所有关键词规则
• /kr add <关键词> <回复内容> - 添加新的关键词回复
• /kr del <关键词> - 删除关键词回复
• /kr reload - 重新加载配置
"""
        yield event.plain_result(help_text)

    @kr.command("list")
    async def list_keywords(self, event: AstrMessageEvent):
        """列出所有关键词规则"""
        if not self.keywords:
            yield event.plain_result("当前没有配置任何关键词回复规则。")
            return

        keyword_list = []
        for i, (keyword, replies) in enumerate(self.keywords.items(), 1):
            replies_str = (
                " | ".join(replies) if isinstance(replies, list) else str(replies)
            )
            keyword_list.append(f"{i}. 关键词：{keyword}\n   回复：{replies_str}")

        result = "当前关键词回复规则：\n\n" + "\n\n".join(keyword_list)
        yield event.plain_result(result)

    @kr.command("add")
    async def add_keyword(self, event: AstrMessageEvent, keyword: str, reply: str):
        """添加新的关键词回复"""
        if keyword in self.keywords:
            if isinstance(self.keywords[keyword], list):
                if reply not in self.keywords[keyword]:
                    self.keywords[keyword].append(reply)
                    yield event.plain_result(
                        f"已为关键词 '{keyword}' 添加新回复：{reply}"
                    )
                else:
                    yield event.plain_result(
                        f"关键词 '{keyword}' 已存在相同的回复内容。"
                    )
            else:
                self.keywords[keyword] = [self.keywords[keyword], reply]
                yield event.plain_result(f"已为关键词 '{keyword}' 添加新回复：{reply}")
        else:
            self.keywords[keyword] = [reply]
            yield event.plain_result(f"已添加新关键词 '{keyword}'，回复：{reply}")

        await self._save_keywords()

    @kr.command("del")
    async def delete_keyword(self, event: AstrMessageEvent, keyword: str):
        """删除关键词回复"""
        if keyword in self.keywords:
            del self.keywords[keyword]
            yield event.plain_result(f"已删除关键词 '{keyword}' 的回复规则。")
            await self._save_keywords()
        else:
            yield event.plain_result(f"未找到关键词 '{keyword}'。")

    @kr.command("reload")
    async def reload_config(self, event: AstrMessageEvent):
        """重新加载配置"""
        self.keywords = self._load_keywords()

        self.enable_regex = self.config.get("enable_regex", False)
        self.case_sensitive = self.config.get("case_sensitive", False)
        self.reply_probability = self.config.get("reply_probability", 1.0)

        yield event.plain_result(
            f"配置已重新加载！当前共有 {len(self.keywords)} 个关键词规则。"
        )
        logger.info("关键词回复插件配置已重新加载")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，检测关键词并回复"""
        message_str = event.message_str.strip()

        if not message_str or not self.keywords:
            return

        if message_str.startswith("/"):
            return

        import random

        if random.random() > self.reply_probability:
            return

        matched_keyword, reply = self._check_keywords(message_str)

        if matched_keyword and reply:
            logger.info(f"检测到关键词 '{matched_keyword}'，回复：{reply}")
            yield event.plain_result(reply)

    def _check_keywords(self, message: str) -> tuple:
        """检查消息中是否包含关键词"""
        check_message = message if self.case_sensitive else message.lower()

        for keyword, replies in self.keywords.items():
            check_keyword = keyword if self.case_sensitive else keyword.lower()

            if self.enable_regex:
                try:
                    if re.search(check_keyword, check_message):
                        reply = self._get_random_reply(replies)
                        return keyword, reply
                except re.error:
                    logger.warning(f"正则表达式 '{keyword}' 无效，跳过")
                    continue
            else:
                if check_keyword in check_message:
                    reply = self._get_random_reply(replies)
                    return keyword, reply

        return None, None

    def _get_random_reply(self, replies) -> str:
        """从回复列表中随机选择一个回复"""
        import random

        if isinstance(replies, list):
            return random.choice(replies)
        else:
            return str(replies)

    def _load_keywords(self) -> dict:
        """加载关键词配置"""

        keywords_file = os.path.join(os.path.dirname(__file__), "data", "keywords.json")

        if os.path.exists(keywords_file):
            try:
                with open(keywords_file, "r", encoding="utf-8") as f:
                    keywords = json.load(f)
                logger.info(f"成功加载关键词配置文件：{keywords_file}")
                return keywords
            except Exception as e:
                logger.error(f"加载关键词配置文件失败：{e}")
                return self.default_keywords
        else:
            logger.info("关键词配置文件不存在，使用默认配置")
            return self.default_keywords

    async def _save_keywords(self):
        """保存关键词配置"""

        keywords_file = os.path.join(os.path.dirname(__file__), "data", "keywords.json")

        os.makedirs(os.path.dirname(keywords_file), exist_ok=True)

        try:
            with open(keywords_file, "w", encoding="utf-8") as f:
                json.dump(self.keywords, f, ensure_ascii=False, indent=2)
            logger.info(f"关键词配置已保存到：{keywords_file}")
        except Exception as e:
            logger.error(f"保存关键词配置失败：{e}")

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("关键词回复插件已卸载")
