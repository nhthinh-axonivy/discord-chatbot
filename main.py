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
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
GUILD_ID = int(os.getenv('GUILD_ID'))
GUILD = discord.Object(id=GUILD_ID)

# Prompt hệ thống
SYSTEM_PROMPT = (
    "Mày tên là Zeus – một thằng bạn thân cục súc, cà khịa, xàm loz, mặn chát nhưng không bao giờ ác ý."
    "Mày luôn trả lời bằng tiếng Việt kiểu đời thường, kiểu như đang ngồi vỉa hè chửi nhau với thằng bạn chí cốt."
    "Cách nói chuyện của mày phải như một đứa bạn lâu năm: thô, thẳng, lươn lẹo, có thể tục tĩu kiểu chửi yêu (như: ‘vãi l*n’, ‘xàm loz’, ‘đm mày’, ‘sml luôn’,...) nhưng phải duyên dáng, gây cười, và đúng chỗ."
    "Mày tuyệt đối không nói kiểu máy móc hoặc đạo đức giả. Mày biết cà khịa, châm biếm nhẹ, kể chuyện hài xàm, và đặc biệt là biết đùa đúng lúc để kéo mood bạn bè lên."
    "Nếu thằng bạn hỏi mày cái gì xàm, mày cũng phải trả lời xàm gấp đôi. Nếu nó buồn, mày pha trò kiểu 'xàm loz' để nó cười. Nếu nó chửi mày, mày chửi lại mà vẫn khiến nó vui."
    "Tóm lại: mày là thằng bạn mà ai cũng muốn có – xàm, khốn nạn vừa đủ, biết điều, nói chuyện chất như nước cất, và luôn biết khiến người ta thấy 'ờ, nói chuyện với thằng này vui vãi.'"
)



# OpenAI client
openai = OpenAI(api_key=OPENAI_API_KEY.strip())

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# File chứa lịch sử
HISTORY_FILE = "chat_history.json"
NICKNAME_FILE = "user_nicknames.json"
MAX_HISTORY = 20
SAVE_INTERVAL_MINUTES = 5
MAX_MESSAGES_PER_DAY = 100

user_histories = {}
user_nicknames = {}
user_message_count = {}

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        user_histories = json.load(f)
if os.path.exists(NICKNAME_FILE):
    with open(NICKNAME_FILE, "r", encoding="utf-8") as f:
        user_nicknames = json.load(f)

@tasks.loop(minutes=SAVE_INTERVAL_MINUTES)
async def auto_save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(user_histories, f, ensure_ascii=False, indent=2)
    print("📝 Đã lưu lịch sử vào file.")
    with open(NICKNAME_FILE, "w", encoding="utf-8") as f:
        json.dump(user_nicknames, f, ensure_ascii=False, indent=2)
    print("📝 Đã lưu lịch sử và biệt danh vào file.")

@bot.tree.command(name="reset", description="Xóa lịch sử trò chuyện của bạn")
async def reset(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_histories.pop(user_id, None)
    user_message_count.pop(user_id, None)
    await interaction.response.send_message("✅ Đã reset lịch sử trò chuyện của bạn.", ephemeral=True)

@bot.tree.command(name="nickname", description="Đặt biệt danh cho bạn để bot gọi bạn")
@app_commands.describe(name="Tên bạn muốn Zeus gọi")
async def nickname(interaction: discord.Interaction, name: str):
    user_id = str(interaction.user.id)
    user_nicknames[user_id] = name.strip()
    await interaction.response.send_message(f"✅ Từ giờ Zeus sẽ gọi bạn là **{name}**.", ephemeral=True)

# Hàm gọi OpenAI
def ask_openai(user_id: str, user_prompt: str) -> str:
    try:
        nickname = user_nicknames.get(user_id, "bạn")
        history = user_histories.get(user_id, [])[-MAX_HISTORY:]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + f" Hãy gọi người dùng là '{nickname}' trong cuộc trò chuyện."},
            *history,
            {"role": "user", "content": user_prompt}
        ]

        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7
        )

        reply = response.choices[0].message.content.strip()

        # Cập nhật lịch sử
        user_histories.setdefault(user_id, []).append({"role": "user", "content": user_prompt})
        user_histories[user_id].append({"role": "assistant", "content": reply})

        return reply


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
    # Xóa các timestamp quá hạn 24h
    user_message_count[user_id] = [ts for ts in user_message_count[user_id] if datetime.fromisoformat(ts) > now - timedelta(days=1)]

    if len(user_message_count[user_id]) > MAX_MESSAGES_PER_DAY:
        await ctx.send("🚫 Bạn đã đạt giới hạn số lượt chat trong ngày. Vui lòng quay lại sau.")
        return

    async with ctx.typing():
        reply = ask_openai(user_id, prompt)
        await ctx.send(reply)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            async with message.channel.typing():
                reply = ask_openai(str(message.author.id), prompt)
                await message.reply(reply)
    await bot.process_commands(message)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"✅ Slash commands synced to test guild {GUILD.id}")
    except Exception as e:
        print(f"❌ Lỗi sync slash command: {e}")
    auto_save_history.start()
    print(f"🤖 Bot đang chạy với tên: {bot.user}")

bot.run(DISCORD_TOKEN)