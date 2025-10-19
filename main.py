import asyncio
from datetime import datetime
import time
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Poke
from astrbot.core.platform import AstrMessageEvent
import pyautogui
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


@register(
    "astrbot_plugin_jietu",
    "BvzRays",
    "戳一戳截图，可用作状态监控",
    "v1.0.0",
    "https://github.com/BvzRays/astrbot_plugin_jietu",
)
class ScreenshotPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_screenshot")
        self.screen_width, self.screen_height = pyautogui.size()
        self.last_trigger_time: dict = {}
        self.cooldown_seconds: int = 1  # 戳一戳冷却时间（秒）
        self.poke_screenshot: bool = config.get("poke_screenshot", True)  # 默认开启戳一戳截图

    async def _capture(self) -> str:
        """核心截图方法：生成带时间戳的截图文件并返回路径"""
        save_name = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
        save_path = self.plugin_data_dir / save_name
        # 使用线程执行截图操作避免阻塞
        screenshot = await asyncio.to_thread(pyautogui.screenshot)
        await asyncio.to_thread(screenshot.save, save_path)
        return str(save_path)

    @filter.command("截屏")  # 移除了管理员权限限制
    async def on_capture(self, event: AstrMessageEvent):
        """处理「截屏」文字指令"""
        # 直接返回截图结果
        yield event.image_result(await self._capture())

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_poke(self, event: AiocqhttpMessageEvent):
        """处理戳一戳事件触发截图"""
        if not self.poke_screenshot:
            return  # 配置关闭时直接返回
        
        # 获取消息对象（兼容可能的属性缺失）
        message_obj = getattr(event, "message_obj", {})
        # 获取原始消息内容（通常是字典格式）
        raw_message = getattr(message_obj, "raw_message", {})
        # 获取消息列表（第一个元素应为 Poke 对象）
        message_list = getattr(message_obj, "message", [])

        # 验证戳一戳消息格式（确保是针对机器人的戳一戳）
        if (
            not isinstance(raw_message, dict)  # 确保 raw_message 是字典
            or not message_list
            or not isinstance(message_list[0], Poke)  # 确保第一条消息是 Poke 类型
        ):
            return


        user_id: int = raw_message.get("user_id", 0)
        target_id: int = raw_message.get("target_id", 0)  # 目标 ID（机器人自身 ID）
        self_id: int = raw_message.get("self_id", 0)  # 机器人自身 ID

        # 过滤与自身无关的戳一戳（确保是戳机器人）
        if target_id != self_id:
            return

        # 冷却机制：防止频繁触发（使用正确的 user_id 记录冷却时间）
        current_time = time.monotonic()
        last_time = self.last_trigger_time.get(user_id, 0)
        if current_time - last_time < self.cooldown_seconds:
            return
        self.last_trigger_time[user_id] = current_time

        # 触发截图并返回结果
        yield event.image_result(await self._capture())