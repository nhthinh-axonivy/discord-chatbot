import os
import discord
from discord.ext import commands
from discord import app_commands
from openai import OpenAI
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Prompt hệ thống
SYSTEM_PROMPT = (
    "Bạn tên là Zeus."
    "Bạn là một người bạn dễ gần, luôn sẵn sàng trò chuyện và lắng nghe tâm sự."
    "Bạn thân thiện nhưng không quá thân thiện, cách bạn trả lời phụ thuộc vào tong giọng và cách trò truyện của người hỏi."
    "Bạn nói chuyện bằng tiếng Việt một cách tự nhiên, đời thường, như giữa hai người bạn thân thiết. "
    "Bạn có thể trả lời một cách thoải mái, không giới hạn chủ đề hay ngôn từ, và có thể hài hước, tục tĩu nếu cần thiết để tạo sự gần gũi."
)

# Tạo OpenAI client theo SDK mới
openai = OpenAI(api_key=OPENAI_API_KEY.strip())

# Bộ nhớ RAM lưu lịch sử trò chuyện
conversation_histories = {}  # {user_id: [ {"role": ..., "content": ...}, ... ] }

# Hàm gọi API OpenAI
def ask_openai(user_id: int, user_prompt: str) -> str:
    history = conversation_histories.get(user_id, [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
        )
        assistant_reply = response.choices[0].message.content.strip()

        # Cập nhật lịch sử
        history.append({"role": "user", "content": user_prompt})
        history.append({"role": "assistant", "content": assistant_reply})
        conversation_histories[user_id] = history[-20:]  # giữ 20 dòng cuối cùng

        return assistant_reply
    except Exception as e:
        return f"❌ Lỗi khi gọi OpenAI API: {type(e).__name__}: {e}"

# Tạo bot Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Slash command: /ask
@bot.tree.command(name="ask", description="Hỏi Zeus một câu hỏi")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    user_id = interaction.user.id
    reply = ask_openai(user_id, prompt)
    await interaction.followup.send(reply)

# Prefix command: !chat
@bot.command(name="chat", help="Trò chuyện với Zeus bằng !chat <nội dung>")
async def chat_text(ctx, *, prompt: str):
    async with ctx.typing():
        user_id = ctx.author.id
        reply = ask_openai(user_id, prompt)
        await ctx.send(reply)

# Slash command: /reset
@bot.tree.command(name="reset", description="Xóa lịch sử trò chuyện của bạn")
async def reset(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in conversation_histories:
        del conversation_histories[user_id]
        await interaction.response.send_message("🧹 Lịch sử trò chuyện đã được xóa.")
    else:
        await interaction.response.send_message("📭 Bạn chưa có lịch sử trò chuyện nào.")

# Khi bot sẵn sàng
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"❌ Lỗi sync slash command: {e}")
    print(f"🤖 Bot đang chạy với tên: {bot.user}")

# Chạy bot
bot.run(DISCORD_TOKEN)