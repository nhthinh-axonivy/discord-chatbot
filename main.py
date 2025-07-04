import os
import json
import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load biến môi trường
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')

# Prompt hệ thống
SYSTEM_PROMPT = (
    "Bạn tên là Zeus."
    "Bạn là một người bạn dễ gần, luôn sẵn sàng trò chuyện và lắng nghe tâm sự."
    "Bạn thân thiện nhưng không quá thân thiện, cách bạn trả lời phụ thuộc vào tông giọng và cách trò chuyện của người hỏi."
    "Bạn nói chuyện bằng tiếng Việt một cách tự nhiên, đời thường, như giữa hai người bạn thân thiết."
    "Bạn có thể trả lời một cách thoải mái, không giới hạn chủ đề hay ngôn từ, và có thể hài hước, tục tĩu nếu cần thiết để tạo sự gần gũi."
)

# OpenAI client
openai = OpenAI(api_key=OPENAI_API_KEY.strip())

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# File chứa lịch sử
HISTORY_FILE = "chat_history.json"
MAX_HISTORY = 20
SAVE_INTERVAL_MINUTES = 5
MAX_MESSAGES_PER_DAY = 100

user_histories = {}
user_message_count = {}

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        user_histories = json.load(f)

@tasks.loop(minutes=SAVE_INTERVAL_MINUTES)
async def auto_save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(user_histories, f, ensure_ascii=False, indent=2)
    print("📝 Đã lưu lịch sử vào file.")

@bot.tree.command(name="reset", description="Xóa lịch sử trò chuyện của bạn")
async def reset(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_histories.pop(user_id, None)
    user_message_count.pop(user_id, None)
    await interaction.response.send_message("✅ Đã reset lịch sử trò chuyện của bạn.", ephemeral=True)


# Hàm gọi OpenAI
def ask_openai(user_id: str, user_prompt: str) -> str:
    history = user_histories.get(user_id, [])[-MAX_HISTORY:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_prompt}]

    try:
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
        )
        assistant_reply = response.choices[0].message.content.strip()
        user_histories.setdefault(user_id, []).append({"role": "user", "content": user_prompt})
        user_histories[user_id].append({"role": "assistant", "content": assistant_reply})

        return assistant_reply
    except Exception as e:
        if "quota" in str(e).lower():
            return "⚠️ Hết hạn mức sử dụng API hoặc key không hợp lệ. Vui lòng kiểm tra lại."
        return f"❌ Lỗi khi gọi OpenAI API: {type(e).__name__}: {e}"

# !chat <nội dung>
@bot.command(name="chat", help="Trò chuyện với Zeus bằng !chat <nội dung>")
async def chat_text(ctx, *, prompt: str):
    user_id = str(ctx.author.id)

    # Giới hạn số lượng message/ngày
    now = datetime.utcnow()
    user_message_count.setdefault(user_id, []).append(now.isoformat())
    user_message_count[user_id] = [ts for ts in user_message_count[user_id] if datetime.fromisoformat(ts) > now - timedelta(days=1)]

    if len(user_message_count[user_id]) > MAX_MESSAGES_PER_DAY:
        await ctx.send("🚫 Bạn đã đạt giới hạn số lượt chat trong ngày. Vui lòng quay lại sau.")
        return

    async with ctx.typing():
        reply = ask_openai(user_id, prompt)
        await ctx.send(reply)

@bot.event
async def on_message(message):
    await bot.process_commands(message)  # Cho phép xử lý lệnh bình thường

    if message.author == bot.user or message.content.startswith("!"):
        return

    if bot.user in message.mentions:
        user_id = str(message.author.id)
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            async with message.channel.typing():
                reply = ask_openai(user_id, prompt)
                await message.channel.send(reply)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"❌ Lỗi sync slash command: {e}")
    auto_save_history.start()
    print(f"🤖 Bot đang chạy với tên: {bot.user}")

bot.run(DISCORD_TOKEN)