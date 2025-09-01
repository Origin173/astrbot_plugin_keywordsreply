from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import re
import os
import json
import random


@register(
    "astrbot_plugin_keywordsreply",
    "Origin173",
    "一个检测到关键词就会回复预定文本的插件",
    "1.1.0",
    "https://github.com/Origin173/astrbot_plugin_keywordsreply",
)
class krPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}

        self.plugin_name = "astrbot_plugin_keywordsreply"
        
        self.default_keywords = {
            "你好": ["你好！", "嗨！", "Hello！"],
            "再见": ["再见！", "拜拜！", "Goodbye！"],
        }

        self.keywords = self._load_keywords()
        self._normalize_keywords()

        self.enable_regex = self.config.get("enable_regex", False)
        self.case_sensitive = self.config.get("case_sensitive", False)
        self.reply_probability = self.config.get("reply_probability", 1.0)

        logger.info(f"关键词回复插件已加载，共 {len(self.keywords)} 个关键词规则")

    @property
    def keywords_file_path(self) -> str:
        """获取关键词配置文件路径"""
        try:
            if hasattr(self.context, 'get_data_dir'):
                data_dir = self.context.get_data_dir(self.plugin_name)
            else:
                data_dir = os.path.join(os.path.dirname(__file__), "data")
                logger.warning("使用备用数据目录方案，建议升级 AstrBot 以使用框架数据管理")
            
            return os.path.join(data_dir, "keywords.json")
        except Exception as e:
            logger.warning(f"无法获取框架数据目录，使用备用方案: {e}")
            return os.path.join(os.path.dirname(__file__), "data", "keywords.json")

    def _normalize_keywords(self):
        """确保所有关键词的回复都是列表格式"""
        for keyword, replies in self.keywords.items():
            if not isinstance(replies, list):
                self.keywords[keyword] = [str(replies)]

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
                    if self._is_safe_regex(check_keyword):
                        if re.search(check_keyword, check_message):
                            reply = self._get_random_reply(replies)
                            return keyword, reply
                    else:
                        logger.warning(f"正则表达式 '{keyword}' 可能存在安全风险，跳过")
                        continue
                except re.error as e:
                    logger.warning(f"正则表达式 '{keyword}' 无效，跳过: {e}")
                    continue
                except Exception as e:
                    logger.error(f"正则表达式匹配时发生未知错误: {e}")
                    continue
            else:
                if check_keyword in check_message:
                    reply = self._get_random_reply(replies)
                    return keyword, reply

        return None, None

    def _is_safe_regex(self, pattern: str) -> bool:
        """正则表达式安全检查"""
        dangerous_patterns = [
            r'\(\?\:',  
            r'\(\?\!', 
            r'\(\?\<',  
            r'\*\+',    
            r'\+\*',    
            r'\*\*',   
            r'\+\+',   
            r'\(\.*\+.*\)\+',  
            r'\{.*\}.*\{.*\}', 
        ]
        
        if len(pattern) > 100:
            return False
            
        for dangerous in dangerous_patterns:
            if re.search(dangerous, pattern):
                return False
                
        return True

    def _get_random_reply(self, replies) -> str:
        """从回复列表中随机选择一个回复"""
        if isinstance(replies, list) and replies:
            return random.choice(replies)
        else:
            return str(replies)

    def _load_keywords(self) -> dict:
        """加载关键词配置"""
        keywords_file = self.keywords_file_path

        if os.path.exists(keywords_file):
            try:
                with open(keywords_file, "r", encoding="utf-8") as f:
                    keywords = json.load(f)
                logger.info(f"成功加载关键词配置文件：{keywords_file}")
                return keywords
            except json.JSONDecodeError as e:
                logger.error(f"关键词配置文件 JSON 格式错误：{e}")
                return self.default_keywords
            except PermissionError as e:
                logger.error(f"无权限读取关键词配置文件：{e}")
                return self.default_keywords
            except FileNotFoundError as e:
                logger.error(f"关键词配置文件未找到：{e}")
                return self.default_keywords
            except Exception as e:
                logger.error(f"加载关键词配置文件时发生未知错误：{e}")
                return self.default_keywords
        else:
            logger.info("关键词配置文件不存在，使用默认配置")
            return self.default_keywords

    async def _save_keywords(self):
        """保存关键词配置"""
        keywords_file = self.keywords_file_path

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(keywords_file), exist_ok=True)
            
            with open(keywords_file, "w", encoding="utf-8") as f:
                json.dump(self.keywords, f, ensure_ascii=False, indent=2)
            logger.info(f"关键词配置已保存到：{keywords_file}")
        except PermissionError as e:
            logger.error(f"无权限写入关键词配置文件：{e}")
        except OSError as e:
            logger.error(f"写入关键词配置文件时发生系统错误：{e}")
        except Exception as e:
            logger.error(f"保存关键词配置时发生未知错误：{e}")

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("关键词回复插件已卸载")
