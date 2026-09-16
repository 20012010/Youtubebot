import os
import json
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import yt_dlp

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8772772179:AAF-3UXZvTwvaUdi6dSh1JYBkgr4Y4hjS00"  # Bot tokeningiz
ADMIN_ID = 5767188230                # Telegram ID
CHANNEL_ID = "@YoutubeeDownload"     # Majburiy obuna kanali
CHANNEL_URL = "https://t.me/YoutubeeDownload"

USERS_FILE = "users.json"
# ====================================================

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(users, f)

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

def get_sub_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Hammaga xabar yuborish", callback_data="admin_broadcast")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun quyidagi kanalga obuna bo'ling:",
            reply_markup=get_sub_keyboard()
        )
        return

    await update.message.reply_text("👋 Salom! Menga YouTube video havolasini yuboring.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("⚙️ **Admin Panel**", reply_markup=get_admin_keyboard())

def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if not await check_subscription(user_id, context):
        await update.message.reply_text("⚠️ Botdan foydalanish uchun kanalga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    # Admin Broadcast
    if user_id == ADMIN_ID and context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        users = load_users()
        success, failed = 0, 0
        status_msg = await update.message.reply_text("⏳ Xabar yuborilmoqda...")
        for u_id in users:
            try:
                await context.bot.copy_message(chat_id=u_id, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
                success += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await status_msg.edit_text(f"✅ **Xabar yuborildi!**\n\nYetib bordi: {success} ta\nXatolik: {failed} ta")
        return

    url = update.message.text
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        await update.message.reply_text("Iltimos, to'g'ri YouTube havolasini yuboring.")
        return

    wait_msg = await update.message.reply_text("🔎 Video ma'lumotlari yuklanmoqda...")

    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_video_info, url)

        title = info.get('title', 'Video')
        channel = info.get('uploader', 'YouTube')
        thumbnail = info.get('thumbnail')
        duration = info.get('duration', 0)
        width = info.get('width', 0)
        height = info.get('height', 0)

        target_resolutions = [240, 360, 480, 720, 1080]
        available_formats = {}

        for f in info.get('formats', []):
            res = f.get('height')
            if res in target_resolutions and res not in available_formats:
                filesize = f.get('filesize') or f.get('filesize_approx')
                if filesize:
                    mb_size = round(filesize / (1024 * 1024), 1)
                    available_formats[res] = f"{mb_size}MB"
                else:
                    available_formats[res] = "~MB"

        caption_text = f"📹 **{title}**\n👤 **{channel}**\n\n"
        for res in sorted(available_formats.keys()):
            caption_text += f"🚀 `{res}p:`  `{available_formats[res]}`\n"
        caption_text += "\n**Yuklab olish formatini tanlang ↓**"

        keyboard = []
        row = []
        for res in sorted(available_formats.keys()):
            row.append(InlineKeyboardButton(f"📺 {res}p", callback_data=f"dl|{res}|video"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("🔊 MP3", callback_data="dl|audio|mp3"),
            InlineKeyboardButton("🖼 Prevyu", callback_data="dl|thumb|image")
        ])

        context.user_data['url'] = url
        context.user_data['thumbnail'] = thumbnail
        context.user_data['duration'] = duration
        context.user_data['width'] = width
        context.user_data['height'] = height

        reply_markup = InlineKeyboardMarkup(keyboard)

        if thumbnail:
            await update.message.reply_photo(photo=thumbnail, caption=caption_text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(caption_text, parse_mode="Markdown", reply_markup=reply_markup)

        await wait_msg.delete()

    except Exception as e:
        await wait_msg.edit_text(f"❌ Ma'lumot olishda xatolik yuz berdi: {str(e)}")

def create_progress_bar(percent):
    filled = int(percent / 10)
    bar = '█' * filled + '░' * (10 - filled)
    return bar

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        if await check_subscription(user_id, context):
            await query.edit_message_text("✅ Obuna tasdiqlandi! Endi YouTube havolasini yuborishingiz mumkin.")
        else:
            await query.answer("❌ Hali kanalga obuna bo'lmadingiz!", show_alert=True)
        return

    elif data == "admin_stats":
        if user_id == ADMIN_ID:
            users = load_users()
            await query.message.reply_text(f"📊 **Bot statistikasi:**\n\nJami foydalanuvchilar: {len(users)} ta")
        return

    elif data == "admin_broadcast":
        if user_id == ADMIN_ID:
            context.user_data['awaiting_broadcast'] = True
            await query.message.reply_text("📢 Yubormoqchi bo'lgan xabaringizni matn yoki rasm/video ko'rinishida yuboring:")
        return

    if data.startswith("dl|"):
        _, opt, media_type = data.split("|")
        url = context.user_data.get('url')

        if not url:
            await query.message.reply_text("❌ Havola eskirgan. Iltimos, havolani qayta yuboring.")
            return

        if opt == "thumb":
            thumb_url = context.user_data.get('thumbnail')
            if thumb_url:
                await query.message.reply_photo(photo=thumb_url, caption="🖼 Video rasmi (Prevyu)")
            return

        msg = await query.message.reply_text("⏳ Yuklash boshlanmoqda...")
        out_file = f"file_{query.message.message_id}"

        main_loop = asyncio.get_running_loop()
        last_update_time = [time.time()]

        def progress_hook(d):
            if d['status'] == 'downloading':
                now = time.time()
                if now - last_update_time[0] > 3.0:
                    last_update_time[0] = now
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    
                    if total > 0:
                        percent = (downloaded / total) * 100
                        bar = create_progress_bar(percent)
                        mb_downloaded = downloaded / (1024 * 1024)
                        mb_total = total / (1024 * 1024)
                        
                        text = (
                            f"📥 **Yuklanmoqda...**\n\n"
                            f"[{bar}] `{percent:.1f}%`\n"
                            f"💾 `{mb_downloaded:.1f}MB / {mb_total:.1f}MB`"
                        )
                    else:
                        text = "📥 **Yuklanmoqda...**"
                    
                    asyncio.run_coroutine_threadsafe(
                        msg.edit_text(text, parse_mode="Markdown"),
                        main_loop
                    )

        if media_type == "mp3":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f"{out_file}.%(ext)s",
                'progress_hooks': [progress_hook],
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
            }
            final_file = f"{out_file}.mp3"
        else:
            ydl_opts = {
                'format': f'bestvideo[height<={opt}][ext=mp4]+bestaudio[ext=m4a]/best[height<={opt}][ext=mp4]/best',
                'outtmpl': f"{out_file}.mp4",
                'progress_hooks': [progress_hook],
                'quiet': True,
            }
            final_file = f"{out_file}.mp4"

        try:
            def extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            await main_loop.run_in_executor(None, extract)

            if os.path.exists(final_file):
                file_size_mb = os.path.getsize(final_file) / (1024 * 1024)
                if file_size_mb > 50:
                    await msg.edit_text(f"❌ Fayl hajmi juda katta ({file_size_mb:.1f} MB). Telegram botlar 50 MB dan katta fayllarni yubora olmaydi.")
                    os.remove(final_file)
                    return

                await msg.edit_text("📤 Telegram'ga yuklanmoqda...")
                with open(final_file, 'rb') as f:
                    if media_type == "mp3":
                        await query.message.reply_audio(
                            audio=f, 
                            caption="🎵 Siz so'ragan MP3 fayl!"
                        )
                    else:
                        duration = context.user_data.get('duration', 0)
                        width = context.user_data.get('width', 0)
                        height = context.user_data.get('height', 0)

                        await query.message.reply_video(
                            video=f, 
                            caption=f"🎬 Video sifati: {opt}p",
                            duration=duration,
                            width=width,
                            height=height,
                            supports_streaming=True
                        )
                await msg.delete()
            else:
                await msg.edit_text("❌ Faylni yuklab bo'lmadi.")

        except Exception as e:
            await msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
        finally:
            if os.path.exists(final_file):
                os.remove(final_file)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()