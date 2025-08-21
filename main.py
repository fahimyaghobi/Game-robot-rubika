import asyncio
from rubka.asynco import Robot
from rubka.context import Message
from rubka.keypad import ChatKeypadBuilder
from collections import deque, defaultdict
from datetime import datetime, timedelta
import json
import os
import random
import string
from pathlib import Path
from typing import Dict, List, Optional

# ایجاد پوشه پروفایل اگر وجود ندارد
if not os.path.exists("profile_pics"):
    os.makedirs("profile_pics")
#توکن را اینجا وارد کنید
bot = Robot(token="BBIJJ0BXNPMYLVPYUKVHDGDFVQAGQJMISSQBKIKFGIUNDJYJOQJFVGTRRCAHDUOI")
#رمز پنل مدیریت اینجا وارد کنید
ADMIN_PASSWORD = "fahimjan"

async def set_com():
    """تنظیم دستورات بات"""
    try:
        result = await bot.set_commands([
            {"command": "start", "description": "شروع ربات بازی"},
            {"command": "exit", "description": "بازگشت به منوی اصلی"},
            {"command": "help", "description": "راهنمای استفاده از ربات"},
            {"command": "admin", "description": "ورود به پنل مدیریت"}
        ])
        print("✅ دستورات بات تنظیم شد")
        return result
    except Exception as e:
        print(f"❌ خطا در تنظیم دستورات: {e}")
        return False

# فایل‌های پایگاه داده
DB_FILE = "game_data.json"
TICKETS_FILE = "tickets.json"

# متغیرهای سراسری
ONLINE_THRESHOLD = timedelta(minutes=5)

# ساختار دیتابیس
def create_user_data():
    """ساخت داده پیش‌فرض کاربر"""
    return {
        "status": "idle",
        "tg_name": "",
        "nickname": "گیمر",
        "games_won": 0,
        "games_lost": 0,
        "total_games": 0,
        "current_room": ""  # مقدار پیش‌فرض (مثلا رشته خالی یا None)
    }

def update_game_stats(uid: str, game_type: str, won: bool):
    """به‌روزرسانی آمار بازی کاربر"""
    try:
        user = get_user(uid)
        
        # آمار کلی
        user["total_games"] += 1
        if won:
            user["games_won"] += 1
            user["win_streak"] += 1
            if user["win_streak"] > user["best_win_streak"]:
                user["best_win_streak"] = user["win_streak"]
        else:
            user["games_lost"] += 1
            user["win_streak"] = 0
        
        # آمار بازی خاص
        if "games_by_type" not in user:
            user["games_by_type"] = {}
        if game_type not in user["games_by_type"]:
            user["games_by_type"][game_type] = {"played": 0, "won": 0}
        
        user["games_by_type"][game_type]["played"] += 1
        if won:
            user["games_by_type"][game_type]["won"] += 1
        
        # بازی محبوب
        max_played = 0
        favorite = None
        for game, stats in user["games_by_type"].items():
            if stats["played"] > max_played:
                max_played = stats["played"]
                favorite = game
        user["favorite_game"] = favorite
        
        # آمار کلی سیستم
        DB["stats"]["total_games_played"] += 1
        if game_type not in DB["stats"]["games_by_type"]:
            DB["stats"]["games_by_type"][game_type] = 0
        DB["stats"]["games_by_type"][game_type] += 1
        
        # آمار روزانه
        today = datetime.now().strftime("%Y-%m-%d")
        if "daily_stats" not in DB["stats"]:
            DB["stats"]["daily_stats"] = {}
        if today not in DB["stats"]["daily_stats"]:
            DB["stats"]["daily_stats"][today] = {"games": 0, "active_users": set()}
        
        DB["stats"]["daily_stats"][today]["games"] += 1
        DB["stats"]["daily_stats"][today]["active_users"].add(uid)
        # تبدیل set به list برای JSON
        DB["stats"]["daily_stats"][today]["active_users"] = list(DB["stats"]["daily_stats"][today]["active_users"])
        
    except Exception as e:
        print(f"❌ خطا در به‌روزرسانی آمار بازی: {e}")

async def show_user_stats(uid: str):
    """نمایش آمار تفصیلی کاربر"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        user = DB["users"][uid]
        
        # محاسبه آمار
        win_rate = 0
        if user["total_games"] > 0:
            win_rate = (user["games_won"] / user["total_games"]) * 100
        
        # تاریخ عضویت
        join_date = "نامشخص"
        if user.get("join_date"):
            try:
                join_dt = datetime.fromisoformat(user["join_date"].replace("Z", ""))
                join_date = join_dt.strftime("%Y/%m/%d")
            except:
                pass
        
        # رتبه کاربر
        all_users = [(uid, data) for uid, data in DB["users"].items() 
                     if isinstance(data, dict) and data.get("total_games", 0) > 0]
        all_users.sort(key=lambda x: x[1].get("games_won", 0), reverse=True)
        
        rank = "نامشخص"
        for i, (user_id, _) in enumerate(all_users):
            if user_id == uid:
                rank = f"{i + 1} از {len(all_users)}"
                break
        
        # آمار بازی‌های مختلف
        games_stats = ""
        game_names = {
            "rock_paper_scissors": "✂️ سنگ کاغذ قیچی",
            "russian_roulette": "🔫 رولت روسی",
            "dice_game": "🎲 بازی تاس", 
            "heads_tails": "🪙 شیر یا خط",
            "flower_money": "👊 گل یا پوچ"
        }
        
        if user.get("games_by_type"):
            for game_type, stats in user["games_by_type"].items():
                game_name = game_names.get(game_type, game_type)
                played = stats.get("played", 0)
                won = stats.get("won", 0)
                game_win_rate = (won / played * 100) if played > 0 else 0
                games_stats += f"\n{game_name}: {played} بازی ({won} برد - {game_win_rate:.1f}%)"
        
        favorite_game = "ندارد"
        if user.get("favorite_game") and user["favorite_game"] in game_names:
            favorite_game = game_names[user["favorite_game"]]
        
        stats_text = f"""📊 **آمار کامل شما**

👤 **نام:** {user["nickname"]}
📅 **عضویت:** {join_date}
🏆 **رتبه:** {rank}

🎮 **آمار بازی:**
   • کل بازی‌ها: {user["total_games"]}
   • برد: {user["games_won"]} 
   • باخت: {user["games_lost"]}
   • درصد برد: {win_rate:.1f}%

🔥 **رکوردها:**
   • برترین پیروزی متوالی: {user.get("best_win_streak", 0)}
   • پیروزی متوالی فعلی: {user.get("win_streak", 0)}

❤️ **بازی محبوب:** {favorite_game}

📈 **آمار تفصیلی:**{games_stats if games_stats else "\\n   هنوز بازی نکرده‌اید"}"""

        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_main", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, stats_text, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش آمار کاربر: {e}")

async def show_admin_stats(uid: str):
    """نمایش آمار تفصیلی ربات برای ادمین"""
    try:
        # اطمینان از ساختار صحیح
        init_db()
        
        # آمار کلی
        total_users = len(DB["users"]) if isinstance(DB["users"], dict) else 0
        online_users = get_online_count()
        active_rooms = len(DB["rooms"]) if isinstance(DB["rooms"], dict) else 0
        total_games = DB["stats"].get("total_games_played", 0)
        
        # آمار بازی‌ها
        games_stats = ""
        game_names = {
            "rock_paper_scissors": "✂️ سنگ کاغذ قیچی",
            "russian_roulette": "🔫 رولت روسی",
            "dice_game": "🎲 بازی تاس",
            "heads_tails": "🪙 شیر یا خط", 
            "flower_money": "👊 گل یا پوچ"
        }
        
        if isinstance(DB["stats"].get("games_by_type"), dict):
            for game_type, count in DB["stats"]["games_by_type"].items():
                if isinstance(count, (int, float)):
                    game_name = game_names.get(game_type, game_type)
                    percentage = (count / total_games * 100) if total_games > 0 else 0
                    games_stats += f"\n   • {game_name}: {count} ({percentage:.1f}%)"
        
        if not games_stats.strip():
            games_stats = "\n   هیچ بازی ثبت نشده"
        
        # آمار روزانه (آخرین 7 روز)
        daily_stats = ""
        if isinstance(DB["stats"].get("daily_stats"), dict):
            today = datetime.now()
            for i in range(7):
                date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                if date in DB["stats"]["daily_stats"]:
                    day_data = DB["stats"]["daily_stats"][date]
                    games_count = day_data.get("games", 0)
                    users_count = len(day_data.get("active_users", []))
                    daily_stats += f"\n   • {date}: {games_count} بازی، {users_count} کاربر"
        
        if not daily_stats.strip():
            daily_stats = "\n   آمار روزانه موجود نیست"
        
        # برترین بازیکنان
        top_players = []
        for uid, user_data in DB["users"].items():
            if isinstance(user_data, dict) and user_data.get("total_games", 0) > 0:
                top_players.append({
                    "name": user_data.get("nickname", "نامشخص"),
                    "wins": user_data.get("games_won", 0),
                    "games": user_data.get("total_games", 0),
                    "streak": user_data.get("best_win_streak", 0)
                })
        
        top_players.sort(key=lambda x: x["wins"], reverse=True)
        top_players_text = ""
        for i, player in enumerate(top_players[:5]):
            win_rate = (player["wins"] / player["games"] * 100) if player["games"] > 0 else 0
            top_players_text += f"\n   {i+1}. {player['name']}: {player['wins']} برد ({win_rate:.1f}%)"
        
        if not top_players_text.strip():
            top_players_text = "\n   بازیکنی یافت نشد"
        
        stats_text = f"""📊 **آمار کامل ربات**

👥 **کاربران:**
   • کل کاربران: {total_users}
   • آنلاین: {online_users}
   • اتاق‌های فعال: {active_rooms}

🎮 **بازی‌ها:**
   • کل بازی‌ها: {total_games}
   • تنوع بازی‌ها: {games_stats}

📅 **آمار هفته (7 روز اخیر):**{daily_stats}

🏆 **برترین بازیکنان:**{top_players_text}

💾 **سیستم:**
   • حجم داده: {len(str(DB))} کاراکتر
   • آخرین بروزرسانی: {datetime.now().strftime('%Y/%m/%d %H:%M')}"""

        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_admin", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, stats_text, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش آمار ادمین: {e}")
        await safe_send_message(uid, "❌ خطا در بارگیری آمار. لطفاً دوباره تلاش کنید.")

async def show_users_list(uid: str):
    """نمایش لیست تفصیلی کاربران"""
    try:
        users_text = "👥 **لیست کاربران:**\n\n"
        
        # اطمینان از وجود کاربران
        if "users" not in DB or not isinstance(DB["users"], dict) or len(DB["users"]) == 0:
            users_text = "👥 هیچ کاربری ثبت نشده است."
        else:
            # مرتب‌سازی بر اساس تعداد برد
            users_list = []
            for user_id, user_data in DB["users"].items():
                if isinstance(user_data, dict):
                    users_list.append((user_id, user_data))
            
            users_list.sort(key=lambda x: x[1].get("games_won", 0), reverse=True)
            
            # محدود کردن به 15 کاربر اول
            display_count = min(15, len(users_list))
            
            for i, (user_id, user_data) in enumerate(users_list[:display_count]):
                try:
                    status = user_data.get("status", "idle")
                    status_emoji = {
                        "idle": "⚪",
                        "searching": "🔍", 
                        "in_room": "🏠",
                        "in_game": "🎮"
                    }.get(status, "⚪")
                    
                    nickname = user_data.get('nickname', 'بی‌نام')
                    games_won = user_data.get('games_won', 0)
                    total_games = user_data.get('total_games', 0)
                    win_rate = (games_won / total_games * 100) if total_games > 0 else 0
                    win_streak = user_data.get('best_win_streak', 0)
                    
                    # آخرین بازدید
                    last_seen = "نامشخص"
                    if user_data.get("last_seen"):
                        try:
                            last_dt = datetime.fromisoformat(user_data["last_seen"].replace("Z", ""))
                            time_diff = datetime.now() - last_dt
                            if time_diff.days > 0:
                                last_seen = f"{time_diff.days} روز پیش"
                            elif time_diff.seconds > 3600:
                                hours = time_diff.seconds // 3600
                                last_seen = f"{hours} ساعت پیش"
                            elif time_diff.seconds > 60:
                                minutes = time_diff.seconds // 60
                                last_seen = f"{minutes} دقیقه پیش"
                            else:
                                last_seen = "آنلاین"
                        except:
                            pass
                    
                    users_text += f"""{status_emoji} **{i+1}. {nickname}**
   🏆 {games_won} برد از {total_games} بازی ({win_rate:.1f}%)
   🔥 بهترین پیروزی متوالی: {win_streak}
   🕒 آخرین بازدید: {last_seen}

"""
                except Exception as e:
                    print(f"خطا در پردازش کاربر {user_id}: {e}")
                    continue
            
            if len(users_list) > display_count:
                users_text += f"... و {len(users_list) - display_count} کاربر دیگر"
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_admin", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, users_text, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش لیست کاربران: {e}")
        await safe_send_message(uid, "❌ خطا در نمایش لیست کاربران")

# حذف توابع تیکت
def safe_save_tickets():
    """حذف شده - تیکت‌ها دیگر وجود ندارند"""
    pass

def safe_load_tickets():
    """حذف شده - تیکت‌ها دیگر وجود ندارند"""
    pass

async def handle_ticket_submission(uid: str, message: str):
    """حذف شده - تیکت‌ها دیگر وجود ندارند"""
    pass

async def show_tickets(uid: str):
    """حذف شده - تیکت‌ها دیگر وجود ندارند"""
    pass

async def show_tickets(uid: str):
    """حذف شده - تیکت‌ها دیگر وجود ندارند"""
    pass

async def handle_reply_ticket_request(uid: str):
    """حذف شده - تیکت‌ها دیگر وجود ندارند"""
    return {
        "current_opponent": None,
        "current_game": None,
        "game_state": {},
        "admin_state": "none",
        "is_admin": False,
        "last_seen": datetime.now().isoformat()
    }

# دیتابیس اصلی
DB = {
    "users": defaultdict(create_user_data),
    "rooms": {},
    "waiting_queue": deque(),
    "online_users": {},
    "tickets": [],
    "stats": {
        "total_games_played": 0,
        "total_users": 0,
        "games_by_type": {}
    }
}

# دکمه‌های اصلی (حذف تیکت)
BTN_RANDOM_OPPONENT = "🎮 حریف شانسی"
BTN_CREATE_ROOM = "🏠 ساخت اتاق"
BTN_JOIN_ROOM = "🔑 ورود به اتاق"
BTN_GAME_RULES = "📚 معرفی بازی‌ها"
BTN_MY_STATS = "📊 آمار من"
BTN_BACK = "🔙 بازگشت"
BTN_EXIT_GAME = "❌ خروج از بازی"
BTN_SUBMIT_TICKET = "🎫 ثبت تیکت"
# بازی‌ها
BTN_ROCK_PAPER_SCISSORS = "✂️ سنگ کاغذ قیچی"
BTN_RUSSIAN_ROULETTE = "🔫 رولت روسی"
BTN_DICE_GAME = "🎲 بازی تاس"
BTN_HEADS_TAILS = "🪙 شیر یا خط"
BTN_FLOWER_OR_MONEY = "👊 گل یا پوچ"

# دکمه‌های ادمین (حذف تیکت)
BTN_ADMIN_BROADCAST = "📢 پیام همگانی"
BTN_ADMIN_STATS = "📊 آمار ربات"
BTN_ADMIN_USERS = "👥 لیست کاربران"
BTN_ADMIN_TICKETS = "📩 مدیریت تیکت‌ها"
def datetime_serializer(obj):
    """تبدیل datetime به رشته برای JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def safe_save_db():
    """ذخیره امن پایگاه داده"""
    try:
        # ایجاد نسخه پشتیبان
        if os.path.exists(DB_FILE):
            backup_file = f"{DB_FILE}.backup"
            if os.path.exists(backup_file):
                os.remove(backup_file)
            os.rename(DB_FILE, backup_file)
        
        serializable_db = {}
        for key, value in DB.items():
            if key == "waiting_queue":
                serializable_db[key] = list(value)
            elif key == "users":
                # تبدیل defaultdict به dict عادی و تبدیل datetime ها
                users_dict = {}
                for uid, user_data in value.items():
                    user_dict = dict(user_data)
                    # تبدیل datetime به string اگر وجود دارد
                    if 'last_seen' in user_dict and isinstance(user_dict['last_seen'], datetime):
                        user_dict['last_seen'] = user_dict['last_seen'].isoformat()
                    users_dict[uid] = user_dict
                serializable_db[key] = users_dict
            elif key == "online_users":
                # تبدیل datetime های online_users به string
                online_dict = {}
                for uid, last_seen in value.items():
                    if isinstance(last_seen, datetime):
                        online_dict[uid] = last_seen.isoformat()
                    else:
                        online_dict[uid] = last_seen
                serializable_db[key] = online_dict
            else:
                serializable_db[key] = value
        
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable_db, f, ensure_ascii=False, indent=2, default=datetime_serializer)
            
        print("✅ پایگاه داده ذخیره شد")
        return True
    except Exception as e:
        print(f"❌ خطا در ذخیره پایگاه داده: {e}")
        # بازگردانی فایل پشتیبان
        if os.path.exists(f"{DB_FILE}.backup"):
            os.rename(f"{DB_FILE}.backup", DB_FILE)
        return False

def safe_load_db():
    """بارگذاری امن پایگاه داده"""
    if not os.path.exists(DB_FILE):
        print("📄 فایل دیتابیس وجود ندارد، از پیش‌فرض استفاده می‌شود")
        return
    
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for key, value in data.items():
            if key == "waiting_queue":
                DB[key] = deque(value)
            elif key == "users":
                DB[key] = defaultdict(create_user_data)
                for uid, user_data in value.items():
                    # اطمینان از وجود همه فیلدها
                    default_data = create_user_data()
                    default_data.update(user_data)
                    DB[key][uid] = default_data
            elif key == "stats":
                # اطمینان از وجود آمار پایه
                default_stats = {
                    "total_games_played": 0,
                    "total_users": 0,
                    "games_by_type": {}
                }
                default_stats.update(value)
                DB[key] = default_stats
            else:
                DB[key] = value
                
        print("✅ پایگاه داده بارگذاری شد")
    except Exception as e:
        print(f"❌ خطا در بارگذاری پایگاه داده: {e}")

def safe_save_tickets():
    """ذخیره امن تیکت‌ها"""
    try:
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(DB["tickets"], f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ خطا در ذخیره تیکت‌ها: {e}")
        return False

def safe_load_tickets():
    """بارگذاری امن تیکت‌ها"""
    if not os.path.exists(TICKETS_FILE):
        DB["tickets"] = []
        return
    
    try:
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            DB["tickets"] = json.load(f)
    except Exception as e:
        print(f"❌ خطا در بارگذاری تیکت‌ها: {e}")
        DB["tickets"] = []

def generate_room_code():
    """تولید کد اتاق 5 رقمی یکتا"""
    max_attempts = 1000
    attempts = 0
    
    while attempts < max_attempts:
        code = ''.join(random.choices(string.digits, k=5))
        if code not in DB["rooms"]:
            return code
        attempts += 1
    
    # در صورت عدم موفقیت، از timestamp استفاده کن
    return str(int(datetime.now().timestamp()))[-5:]

def update_activity(uid: str):
    """به‌روزرسانی زمان فعالیت کاربر"""
    try:
        DB["online_users"][uid] = datetime.now()
        if uid in DB["users"]:
            DB["users"][uid]["last_seen"] = datetime.now().isoformat()
    except Exception as e:
        print(f"❌ خطا در به‌روزرسانی فعالیت {uid}: {e}")

def get_online_count():
    """تعداد کاربران آنلاین"""
    try:
        now = datetime.now()
        return sum(1 for last_seen in DB["online_users"].values() 
                  if now - last_seen < ONLINE_THRESHOLD)
    except Exception as e:
        print(f"❌ خطا در محاسبه تعداد آنلاین: {e}")
        return 0

def cleanup_inactive_users():
    """پاکسازی کاربران غیرفعال"""
    try:
        now = datetime.now()
        inactive_users = []
        
        for uid, last_seen in DB["online_users"].items():
            if now - last_seen > timedelta(hours=1):
                inactive_users.append(uid)
        
        for uid in inactive_users:
            del DB["online_users"][uid]
            if uid in DB["users"]:
                user = DB["users"][uid]
                if user["status"] == "searching" and uid in DB["waiting_queue"]:
                    DB["waiting_queue"].remove(uid)
                    user["status"] = "idle"
        
        print(f"🧹 {len(inactive_users)} کاربر غیرفعال پاکسازی شد")
    except Exception as e:
        print(f"❌ خطا در پاکسازی: {e}")

async def safe_send_message(uid: str, text: str, keypad=None):
    """ارسال امن پیام"""
    try:
        if keypad:
            await bot.send_message(uid, text, chat_keypad=keypad)
        else:
            await bot.send_message(uid, text)
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیام به {uid}: {e}")
        return False

async def send_main_menu(uid: str, text: str = "🎮 منوی اصلی بازی"):
    """ارسال منوی اصلی"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        user = DB["users"][uid]
        builder = ChatKeypadBuilder()
        
        if user["status"] == "in_game":
            builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
        elif user["status"] == "in_room":
            builder.row(builder.button(id="game_selection", text="🎯 انتخاب بازی"))
            builder.row(builder.button(id="leave_room", text="🚪 ترک اتاق"))
        else:
            builder.row(builder.button(id="random_opponent", text=BTN_RANDOM_OPPONENT))
            builder.row(
                builder.button(id="create_room", text=BTN_CREATE_ROOM),
                builder.button(id="join_room", text=BTN_JOIN_ROOM)
            )
            builder.row(
                builder.button(id="game_rules", text=BTN_GAME_RULES),
                builder.button(id="my_stats", text=BTN_MY_STATS)
            )
            builder.row(builder.button(id="submit_ticket", text=BTN_SUBMIT_TICKET))

        keypad = builder.build(resize_keyboard=True)
        await safe_send_message(uid, text, keypad)
    except Exception as e:
        print(f"❌ خطا در ارسال منوی اصلی به {uid}: {e}")

async def send_game_selection_menu(uid: str, text: str = "🎯 کدام بازی را انتخاب می‌کنید؟"):
    """منوی انتخاب بازی"""
    try:
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="rps", text=BTN_ROCK_PAPER_SCISSORS))
        builder.row(builder.button(id="roulette", text=BTN_RUSSIAN_ROULETTE))
        builder.row(builder.button(id="dice", text=BTN_DICE_GAME))
        builder.row(builder.button(id="heads_tails", text=BTN_HEADS_TAILS))
        builder.row(builder.button(id="flower_money", text=BTN_FLOWER_OR_MONEY))
        builder.row(builder.button(id="back_to_main", text=BTN_BACK))
        
        keypad = builder.build(resize_keyboard=True)
        await safe_send_message(uid, text, keypad)
    except Exception as e:
        print(f"❌ خطا در ارسال منوی بازی به {uid}: {e}")

async def send_admin_menu(uid: str):
    """ارسال منوی ادمین"""
    try:
        if uid not in DB["users"] or not DB["users"][uid].get("is_admin"):
            await safe_send_message(uid, "❌ شما دسترسی ادمین ندارید!")
            return
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="admin_broadcast", text=BTN_ADMIN_BROADCAST))
        builder.row(builder.button(id="admin_stats", text=BTN_ADMIN_STATS))
        builder.row(builder.button(id="admin_users", text=BTN_ADMIN_USERS))
        builder.row(builder.button(id="admin_tickets", text=BTN_ADMIN_TICKETS))
        builder.row(builder.button(id="back_to_main", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, "🔐 **پنل مدیریت**\n\nبه پنل مدیریت خوش آمدید!", keypad)
    except Exception as e:
        print(f"❌ خطا در ارسال منوی ادمین: {e}")

async def start_random_search(uid: str):
    """شروع جستجوی حریف شانسی"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        user = DB["users"][uid]
        user["status"] = "searching"
        
        # پاکسازی صف از کاربران غیرفعال
        active_queue = deque()
        while DB["waiting_queue"]:
            other_uid = DB["waiting_queue"].popleft()
            if (other_uid in DB["online_users"] and 
                other_uid != uid and 
                other_uid in DB["users"] and 
                DB["users"][other_uid]["status"] == "searching"):
                active_queue.append(other_uid)
        
        DB["waiting_queue"] = active_queue
        
        # اگر کاربری در صف است، آنها را متصل کن
        if len(DB["waiting_queue"]) > 0:
            opponent = DB["waiting_queue"].popleft()
            await match_players(uid, opponent)
            return
        
        # وگرنه به صف اضافه کن
        DB["waiting_queue"].append(uid)
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="cancel_search", text="❌ لغو جستجو"))
        keypad = builder.build(resize_keyboard=True)
        await safe_send_message(uid, "🔍 در حال جستجوی حریف...", keypad)
        
    except Exception as e:
        print(f"❌ خطا در شروع جستجو برای {uid}: {e}")

async def match_players(uid1: str, uid2: str):
    """اتصال دو بازیکن"""
    try:
        # اطمینان از وجود هر دو کاربر
        for uid in [uid1, uid2]:
            if uid not in DB["users"]:
                DB["users"][uid] = create_user_data()
        
        room_code = generate_room_code()
        DB["rooms"][room_code] = {
            "players": [uid1, uid2],
            "owner": uid1,
            "current_game": None,
            "created_at": datetime.now().isoformat()
        }
        
        for uid in [uid1, uid2]:
            user = DB["users"][uid]
            user["status"] = "in_room"
            user["current_room"] = room_code
            user["current_opponent"] = uid2 if uid == uid1 else uid1
        
        user1_name = DB["users"][uid1]["nickname"]
        user2_name = DB["users"][uid2]["nickname"]
        
        await send_game_selection_menu(uid1, f"✅ شما با {user2_name} متصل شدید!")
        await send_game_selection_menu(uid2, f"✅ شما با {user1_name} متصل شدید!")
        
    except Exception as e:
        print(f"❌ خطا در اتصال بازیکنان {uid1}, {uid2}: {e}")

async def create_room(uid: str):
    """ساخت اتاق جدید"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        room_code = generate_room_code()
        DB["rooms"][room_code] = {
            "players": [uid],
            "owner": uid,
            "current_game": None,
            "created_at": datetime.now().isoformat()
        }
        
        user = DB["users"][uid]
        user["status"] = "in_room"
        user["current_room"] = room_code
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_main", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(
            uid, 
            f"🏠 اتاق شما ساخته شد!\n\n🔑 **کد اتاق:** `{room_code}`\n\n"
            f"این کد را با دوست خود به اشتراک بگذارید تا وارد اتاق شود.",
            keypad
        )
    except Exception as e:
        print(f"❌ خطا در ساخت اتاق برای {uid}: {e}")

async def join_room(uid: str, room_code: str):
    """ورود به اتاق"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        room_code = room_code.strip()
        
        if room_code not in DB["rooms"]:
            await safe_send_message(uid, "❌ اتاق با این کد یافت نشد!")
            await send_main_menu(uid)
            return
        
        room = DB["rooms"][room_code]
        
        if len(room["players"]) >= 2:
            await safe_send_message(uid, "❌ این اتاق پر است!")
            await send_main_menu(uid)
            return
        
        if uid in room["players"]:
            await safe_send_message(uid, "❌ شما قبلاً در این اتاق هستید!")
            await send_main_menu(uid)
            return
        
        room["players"].append(uid)
        user = DB["users"][uid]
        user["status"] = "in_room"
        user["current_room"] = room_code
        
        if len(room["players"]) >= 2:
            user["current_opponent"] = room["players"][0]
            
            opponent = DB["users"][room["players"][0]]
            opponent["current_opponent"] = uid
            
            user_name = user["nickname"]
            owner_name = opponent["nickname"]
            
            await send_game_selection_menu(uid, f"✅ شما وارد اتاق {owner_name} شدید!")
            await send_game_selection_menu(room["players"][0], f"✅ {user_name} وارد اتاق شما شد!")
        else:
            await safe_send_message(uid, f"✅ وارد اتاق شدید. منتظر بازیکن دوم...")
        
    except Exception as e:
        print(f"❌ خطا در ورود به اتاق برای {uid}: {e}")

# بازی‌ها

async def start_rock_paper_scissors(uid: str):
    """شروع بازی سنگ کاغذ قیچی"""
    try:
        if uid not in DB["users"]:
            return
        
        opponent = DB["users"][uid].get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            await safe_send_message(uid, "❌ حریفی یافت نشد!")
            return
        
        for player_id in [uid, opponent]:
            user = DB["users"][player_id]
            user["status"] = "in_game"
            user["current_game"] = "rock_paper_scissors"
            user["game_state"] = {"choice": None, "round": 1}
        
        # به‌روزرسانی آمار
        DB["stats"]["total_games_played"] += 1
        if "rock_paper_scissors" not in DB["stats"]["games_by_type"]:
            DB["stats"]["games_by_type"]["rock_paper_scissors"] = 0
        DB["stats"]["games_by_type"]["rock_paper_scissors"] += 1
        
        builder = ChatKeypadBuilder()
        builder.row(
            builder.button(id="rock", text="🗿 سنگ"),
            builder.button(id="paper", text="📄 کاغذ"),
            builder.button(id="scissors", text="✂️ قیچی")
        )
        builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
        keypad = builder.build(resize_keyboard=True)
        
        message = "✂️ **سنگ کاغذ قیچی**\n\nانتخاب خود را بکنید:"
        await safe_send_message(uid, message, keypad)
        await safe_send_message(opponent, message, keypad)
        
    except Exception as e:
        print(f"❌ خطا در شروع سنگ کاغذ قیچی: {e}")

async def handle_rps_choice(uid: str, choice: str):
    """پردازش انتخاب در سنگ کاغذ قیچی"""
    try:
        if uid not in DB["users"]:
            return
        
        opponent = DB["users"][uid].get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            return
        
        user = DB["users"][uid]
        opponent_user = DB["users"][opponent]
        
        user["game_state"]["choice"] = choice
        
        if opponent_user["game_state"].get("choice"):
            # هر دو انتخاب کرده‌اند
            user_choice = user["game_state"]["choice"]
            opponent_choice = opponent_user["game_state"]["choice"]
            
            result = determine_rps_winner(user_choice, opponent_choice)
            
            choice_emoji = {"rock": "🗿", "paper": "📄", "scissors": "✂️"}
            
            if result == "tie":
                message = (f"🤝 **مساوی!**\n\n"
                          f"شما: {choice_emoji[user_choice]}\n"
                          f"حریف: {choice_emoji[opponent_choice]}\n\n"
                          f"دور بعدی...")
                opponent_message = message
            elif result == "win":
                message = (f"🎉 **شما برنده شدید!**\n\n"
                          f"شما: {choice_emoji[user_choice]}\n" 
                          f"حریف: {choice_emoji[opponent_choice]}")
                opponent_message = (f"😔 **شما باختید!**\n\n"
                                   f"شما: {choice_emoji[opponent_choice]}\n"
                                   f"حریف: {choice_emoji[user_choice]}")
                user["games_won"] += 1
                opponent_user["games_lost"] += 1
            else:
                message = (f"😔 **شما باختید!**\n\n"
                          f"شما: {choice_emoji[user_choice]}\n"
                          f"حریف: {choice_emoji[opponent_choice]}")
                opponent_message = (f"🎉 **شما برنده شدید!**\n\n"
                                   f"شما: {choice_emoji[opponent_choice]}\n"
                                   f"حریف: {choice_emoji[user_choice]}")
                user["games_lost"] += 1
                opponent_user["games_won"] += 1
            
            await safe_send_message(uid, message)
            await safe_send_message(opponent, opponent_message)
            
            if result != "tie":
                # بازی تمام شد
                for player_id in [uid, opponent]:
                    DB["users"][player_id]["total_games"] += 1
                    DB["users"][player_id]["game_state"] = {}
                
                await suggest_rematch(uid, opponent)
            else:
                # ادامه بازی
                for player_id in [uid, opponent]:
                    DB["users"][player_id]["game_state"]["choice"] = None
                
                builder = ChatKeypadBuilder()
                builder.row(
                    builder.button(id="rock", text="🗿 سنگ"),
                    builder.button(id="paper", text="📄 کاغذ"), 
                    builder.button(id="scissors", text="✂️ قیچی")
                )
                builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
                keypad = builder.build(resize_keyboard=True)
                
                await safe_send_message(uid, "انتخاب خود را برای دور بعد بکنید:", keypad)
                await safe_send_message(opponent, "انتخاب خود را برای دور بعد بکنید:", keypad)
        else:
            await safe_send_message(uid, "✅ انتخاب شما ثبت شد. منتظر حریف...")
            
    except Exception as e:
        print(f"❌ خطا در پردازش انتخاب RPS: {e}")

def determine_rps_winner(choice1: str, choice2: str) -> str:
    """تعیین برنده سنگ کاغذ قیچی"""
    if choice1 == choice2:
        return "tie"
    
    winning_combinations = {
        ("rock", "scissors"): True,
        ("paper", "rock"): True,
        ("scissors", "paper"): True
    }
    
    return "win" if winning_combinations.get((choice1, choice2), False) else "lose"

async def start_russian_roulette(uid: str):
    """شروع رولت روسی"""
    try:
        if uid not in DB["users"]:
            return
        
        opponent = DB["users"][uid].get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            await safe_send_message(uid, "❌ حریفی یافت نشد!")
            return
        
        # یک گلوله مشترک برای هر دو بازیکن
        bullet_position = random.randint(1, 6)
        current_turn = 1
        
        for player_id in [uid, opponent]:
            user = DB["users"][player_id]
            user["status"] = "in_game"
            user["current_game"] = "russian_roulette"
            user["game_state"] = {
                "bullet_position": bullet_position,
                "current_turn": current_turn,
                "alive": True,
                "my_turn": False
            }
        
        # به‌روزرسانی آمار
        DB["stats"]["total_games_played"] += 1
        if "russian_roulette" not in DB["stats"]["games_by_type"]:
            DB["stats"]["games_by_type"]["russian_roulette"] = 0
        DB["stats"]["games_by_type"]["russian_roulette"] += 1
        
        # تعیین نوبت اول
        first_player = random.choice([uid, opponent])
        DB["users"][first_player]["game_state"]["my_turn"] = True
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="pull_trigger", text="🔫 شلیک"))
        builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
        keypad = builder.build(resize_keyboard=True)
        
        if first_player == uid:
            await safe_send_message(uid, "🔫 **رولت روسی**\n\nنوبت شما است. شلیک کنید!", keypad)
            await safe_send_message(opponent, "🔫 **رولت روسی**\n\nنوبت حریف شما است...")
        else:
            await safe_send_message(opponent, "🔫 **رولت روسی**\n\nنوبت شما است. شلیک کنید!", keypad)
            await safe_send_message(uid, "🔫 **رولت روسی**\n\nنوبت حریف شما است...")
            
    except Exception as e:
        print(f"❌ خطا در شروع رولت روسی: {e}")

async def handle_russian_roulette(uid: str):
    """پردازش رولت روسی"""
    try:
        if uid not in DB["users"]:
            return
        
        user = DB["users"][uid]
        opponent = user.get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            return
        
        opponent_user = DB["users"][opponent]
        
        if not user["game_state"].get("my_turn"):
            await safe_send_message(uid, "❌ نوبت شما نیست!")
            return
        
        current_turn = user["game_state"]["current_turn"]
        bullet_position = user["game_state"]["bullet_position"]
        
        if current_turn == bullet_position:
            # گلوله اومد!
            user["games_lost"] += 1
            opponent_user["games_won"] += 1
            
            await safe_send_message(uid, "💥 **بنگ!** شما باختید!")
            await safe_send_message(opponent, "🎉 **شما برنده شدید!** گلوله به حریف خورد.")
            
            for player_id in [uid, opponent]:
                DB["users"][player_id]["total_games"] += 1
            
            await suggest_rematch(uid, opponent)
        else:
            # خالی بود - نوبت حریف
            user["game_state"]["my_turn"] = False
            user["game_state"]["current_turn"] += 1
            
            opponent_user["game_state"]["my_turn"] = True
            opponent_user["game_state"]["current_turn"] = current_turn + 1
            
            await safe_send_message(uid, f"😅 **کلیک خالی!** ({current_turn}/6)")
            await safe_send_message(opponent, "😰 حریف زنده ماند! نوبت شما...")
            
            # نوبت حریف
            builder = ChatKeypadBuilder()
            builder.row(builder.button(id="pull_trigger", text="🔫 شلیک"))
            builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
            keypad = builder.build(resize_keyboard=True)
            
            await safe_send_message(opponent, "🔫 نوبت شما!", keypad)
            
    except Exception as e:
        print(f"❌ خطا در پردازش رولت روسی: {e}")

async def start_dice_game(uid: str):
    """شروع بازی تاس"""
    try:
        if uid not in DB["users"]:
            return
        
        opponent = DB["users"][uid].get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            await safe_send_message(uid, "❌ حریفی یافت نشد!")
            return
        
        for player_id in [uid, opponent]:
            user = DB["users"][player_id]
            user["status"] = "in_game"
            user["current_game"] = "dice_game"
            user["game_state"] = {"rolled": False, "result": 0}
        
        # به‌روزرسانی آمار
        DB["stats"]["total_games_played"] += 1
        if "dice_game" not in DB["stats"]["games_by_type"]:
            DB["stats"]["games_by_type"]["dice_game"] = 0
        DB["stats"]["games_by_type"]["dice_game"] += 1
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="roll_dice", text="🎲 انداختن تاس"))
        builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
        keypad = builder.build(resize_keyboard=True)
        
        message = ("🎲 **بازی تاس**\n\n"
                  "تاس خود را بیندازید!\n"
                  "بالاترین عدد برنده است.")
        
        await safe_send_message(uid, message, keypad)
        await safe_send_message(opponent, message, keypad)
        
    except Exception as e:
        print(f"❌ خطا در شروع بازی تاس: {e}")

async def handle_dice_game(uid: str):
    """پردازش بازی تاس"""
    try:
        if uid not in DB["users"]:
            return
        
        result = random.randint(1, 6)
        user = DB["users"][uid]
        user["game_state"]["result"] = result
        user["game_state"]["rolled"] = True
        
        opponent = user.get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            return
        
        opponent_user = DB["users"][opponent]
        
        await safe_send_message(uid, f"🎲 تاس شما: **{result}**")
        
        if opponent_user["game_state"].get("rolled"):
            # هر دو انداختند
            opponent_result = opponent_user["game_state"]["result"]
            
            if result > opponent_result:
                await safe_send_message(uid, f"🎉 شما برنده شدید! ({result} > {opponent_result})")
                await safe_send_message(opponent, f"😔 شما باختید! ({opponent_result} < {result})")
                user["games_won"] += 1
                opponent_user["games_lost"] += 1
            elif result < opponent_result:
                await safe_send_message(uid, f"😔 شما باختید! ({result} < {opponent_result})")
                await safe_send_message(opponent, f"🎉 شما برنده شدید! ({opponent_result} > {result})")
                user["games_lost"] += 1
                opponent_user["games_won"] += 1
            else:
                await safe_send_message(uid, f"🤝 مساوی! ({result} = {opponent_result})")
                await safe_send_message(opponent, f"🤝 مساوی! ({opponent_result} = {result})")
            
            if result != opponent_result:
                for player_id in [uid, opponent]:
                    DB["users"][player_id]["total_games"] += 1
                await suggest_rematch(uid, opponent)
            else:
                # مساوی - دور جدید
                for player_id in [uid, opponent]:
                    DB["users"][player_id]["game_state"] = {"rolled": False, "result": 0}
                
                builder = ChatKeypadBuilder()
                builder.row(builder.button(id="roll_dice", text="🎲 انداختن تاس"))
                builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
                keypad = builder.build(resize_keyboard=True)
                
                await safe_send_message(uid, "🎲 دور جدید!", keypad)
                await safe_send_message(opponent, "🎲 دور جدید!", keypad)
        else:
            await safe_send_message(opponent, f"حریف تاسش را انداخت. نوبت شما!")
            
    except Exception as e:
        print(f"❌ خطا در پردازش بازی تاس: {e}")

async def start_heads_tails(uid: str):
    """شروع شیر یا خط"""
    try:
        if uid not in DB["users"]:
            return
        
        opponent = DB["users"][uid].get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            await safe_send_message(uid, "❌ حریفی یافت نشد!")
            return
        
        for player_id in [uid, opponent]:
            user = DB["users"][player_id]
            user["status"] = "in_game"
            user["current_game"] = "heads_tails"
            user["game_state"] = {"choice": None}
        
        # به‌روزرسانی آمار
        DB["stats"]["total_games_played"] += 1
        if "heads_tails" not in DB["stats"]["games_by_type"]:
            DB["stats"]["games_by_type"]["heads_tails"] = 0
        DB["stats"]["games_by_type"]["heads_tails"] += 1
        
        builder = ChatKeypadBuilder()
        builder.row(
            builder.button(id="heads", text="🦁 شیر"),
            builder.button(id="tails", text="➖ خط")
        )
        builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
        keypad = builder.build(resize_keyboard=True)
        
        message = ("🪙 **شیر یا خط**\n\n"
                  "انتخاب خود را بکنید:")
        
        await safe_send_message(uid, message, keypad)
        await safe_send_message(opponent, message, keypad)
        
    except Exception as e:
        print(f"❌ خطا در شروع شیر یا خط: {e}")

async def handle_heads_tails(uid: str, choice: str):
    """پردازش شیر یا خط"""
    try:
        if uid not in DB["users"]:
            return
        
        user = DB["users"][uid]
        user["game_state"]["choice"] = choice
        
        opponent = user.get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            return
        
        opponent_user = DB["users"][opponent]
        
        if opponent_user["game_state"].get("choice"):
            # هر دو انتخاب کردند
            coin_result = random.choice(["heads", "tails"])
            result_text = "🦁 شیر" if coin_result == "heads" else "➖ خط"
            
            user_won = (choice == coin_result)
            opponent_won = (opponent_user["game_state"]["choice"] == coin_result)
            
            if user_won and not opponent_won:
                await safe_send_message(uid, f"🎉 برنده شدید! نتیجه: {result_text}")
                await safe_send_message(opponent, f"😔 باختید! نتیجه: {result_text}")
                user["games_won"] += 1
                opponent_user["games_lost"] += 1
            elif opponent_won and not user_won:
                await safe_send_message(uid, f"😔 باختید! نتیجه: {result_text}")
                await safe_send_message(opponent, f"🎉 برنده شدید! نتیجه: {result_text}")
                user["games_lost"] += 1
                opponent_user["games_won"] += 1
            else:
                # هر دو درست یا هر دو غلط
                await safe_send_message(uid, f"🤝 مساوی! نتیجه: {result_text}")
                await safe_send_message(opponent, f"🤝 مساوی! نتیجه: {result_text}")
            
            if user_won != opponent_won:
                for player_id in [uid, opponent]:
                    DB["users"][player_id]["total_games"] += 1
                await suggest_rematch(uid, opponent)
            else:
                # دور جدید
                await start_heads_tails(uid)
        else:
            await safe_send_message(uid, "✅ انتخاب شما ثبت شد. منتظر حریف...")
            
    except Exception as e:
        print(f"❌ خطا در پردازش شیر یا خط: {e}")

async def start_flower_money(uid: str):
    """شروع گل یا پوچ"""
    try:
        if uid not in DB["users"]:
            return
        
        opponent = DB["users"][uid].get("current_opponent")
        if not opponent or opponent not in DB["users"]:
            await safe_send_message(uid, "❌ حریفی یافت نشد!")
            return
        
        # تعیین اینکه کدام بازیکن مخفی کار است
        hider = random.choice([uid, opponent])
        guesser = opponent if hider == uid else uid
        
        for player_id in [uid, opponent]:
            user = DB["users"][player_id]
            user["status"] = "in_game" 
            user["current_game"] = "flower_money"
            user["game_state"] = {
                "role": "hider" if player_id == hider else "guesser",
                "choice": None,
                "guess": None
            }
        
        # به‌روزرسانی آمار
        DB["stats"]["total_games_played"] += 1
        if "flower_money" not in DB["stats"]["games_by_type"]:
            DB["stats"]["games_by_type"]["flower_money"] = 0
        DB["stats"]["games_by_type"]["flower_money"] += 1
        
        # پیام برای مخفی کار
        builder_hider = ChatKeypadBuilder()
        builder_hider.row(
            builder_hider.button(id="left_hand", text="👊 دست چپ"),
            builder_hider.button(id="right_hand", text="👊 دست راست")
        )
        builder_hider.row(builder_hider.button(id="exit_game", text=BTN_EXIT_GAME))
        keypad_hider = builder_hider.build(resize_keyboard=True)
        
        await safe_send_message(
            hider,
            "👊 **گل یا پوچ**\n\nشما گل را مخفی می‌کنید!\nگل را در کدام دست قرار می‌دهید؟",
            keypad_hider
        )
        
        await safe_send_message(
            guesser,
            "👊 **گل یا پوچ**\n\nحریف شما گل را در یکی از دست‌هایش مخفی کرده.\nمنتظر انتخاب حریف..."
        )
        
    except Exception as e:
        print(f"❌ خطا در شروع گل یا پوچ: {e}")

async def handle_flower_money(uid: str, action: str):
    """پردازش گل یا پوچ"""
    try:
        if uid not in DB["users"]:
            return
        
        user = DB["users"][uid]
        game_state = user["game_state"]
        opponent = user.get("current_opponent")
        
        if not opponent or opponent not in DB["users"]:
            return
        
        if game_state["role"] == "hider" and action in ["left_hand", "right_hand"]:
            choice = "left" if action == "left_hand" else "right"
            user["game_state"]["choice"] = choice
            
            # حالا حدس زن باید انتخاب کند
            builder = ChatKeypadBuilder()
            builder.row(
                builder.button(id="guess_left", text="👊 دست چپ"),
                builder.button(id="guess_right", text="👊 دست راست")
            )
            builder.row(builder.button(id="exit_game", text=BTN_EXIT_GAME))
            keypad = builder.build(resize_keyboard=True)
            
            await safe_send_message(uid, "✅ انتخاب شما ثبت شد. منتظر حدس حریف...")
            await safe_send_message(opponent, "👊 گل در کدام دست است؟", keypad)
            
        elif game_state["role"] == "guesser" and action in ["guess_left", "guess_right"]:
            guess = "left" if action == "guess_left" else "right"
            
            opponent_user = DB["users"][opponent]
            actual_choice = opponent_user["game_state"]["choice"]
            
            if guess == actual_choice:
                # حدس درست
                await safe_send_message(uid, "🎉 **آفرین!** گل را پیدا کردید!")
                await safe_send_message(opponent, "😔 **حریف گل را پیدا کرد!**")
                user["games_won"] += 1
                opponent_user["games_lost"] += 1
            else:
                # حدس غلط
                await safe_send_message(uid, "😔 **اشتباه!** گل در دست دیگر بود.")
                await safe_send_message(opponent, "🎉 **حریف نتوانست پیدا کند!**")
                user["games_lost"] += 1
                opponent_user["games_won"] += 1
            
            for player_id in [uid, opponent]:
                DB["users"][player_id]["total_games"] += 1
            
            await suggest_rematch(uid, opponent)
            
    except Exception as e:
        print(f"❌ خطا در پردازش گل یا پوچ: {e}")

async def suggest_rematch(uid: str, opponent: str):
    """پیشنهاد بازی مجدد"""
    try:
        builder = ChatKeypadBuilder()
        builder.row(
            builder.button(id="rematch_yes", text="✅ بازی دوباره"),
            builder.button(id="rematch_no", text="❌ خیر")
        )
        keypad = builder.build(resize_keyboard=True)
        
        message = "🔄 آیا می‌خواهید دوباره بازی کنید?"
        
        for player_id in [uid, opponent]:
            if player_id in DB["users"]:
                await safe_send_message(player_id, message, keypad)
                
    except Exception as e:
        print(f"❌ خطا در پیشنهاد بازی مجدد: {e}")

async def exit_game(uid: str):
    """خروج از بازی"""
    try:
        if uid not in DB["users"]:
            return
        
        user = DB["users"][uid]
        opponent = user.get("current_opponent")
        
        user["status"] = "in_room" if user.get("current_room") else "idle"
        user["current_game"] = None
        user["game_state"] = {}
        
        if opponent and opponent in DB["users"]:
            opponent_user = DB["users"][opponent]
            opponent_user["status"] = "in_room" if opponent_user.get("current_room") else "idle"
            opponent_user["current_game"] = None
            opponent_user["game_state"] = {}
            
            await safe_send_message(opponent, "❌ حریف از بازی خارج شد.")
            if opponent_user["status"] == "in_room":
                await send_game_selection_menu(opponent, "🎮 بازی دیگری انتخاب کنید:")
            else:
                await send_main_menu(opponent)
        
        if user["status"] == "in_room":
            await send_game_selection_menu(uid, "🎮 بازی دیگری انتخاب کنید:")
        else:
            await send_main_menu(uid)
            
    except Exception as e:
        print(f"❌ خطا در خروج از بازی: {e}")

async def leave_room(uid: str):
    """ترک اتاق"""
    try:
        if uid not in DB["users"]:
            return
        
        user = DB["users"][uid]
        room_code = user.get("current_room")
        opponent = user.get("current_opponent")
        
        if room_code and room_code in DB["rooms"]:
            room = DB["rooms"][room_code]
            if uid in room["players"]:
                room["players"].remove(uid)
            
            if len(room["players"]) == 0:
                del DB["rooms"][room_code]
        
        user["status"] = "idle"
        user["current_room"] = None
        user["current_opponent"] = None
        user["current_game"] = None
        user["game_state"] = {}
        
        if opponent and opponent in DB["users"]:
            opponent_user = DB["users"][opponent]
            opponent_user["current_opponent"] = None
            await safe_send_message(opponent, "❌ حریف اتاق را ترک کرد.")
            await send_main_menu(opponent)
        
        await send_main_menu(uid, "🚪 شما از اتاق خارج شدید.")
        
    except Exception as e:
        print(f"❌ خطا در ترک اتاق: {e}")

async def show_game_rules(uid: str):
    """نمایش قوانین بازی‌ها"""
    try:
        rules = """📚 **معرفی بازی‌ها**

✂️ **سنگ کاغذ قیچی**
- سنگ قیچی را می‌شکند
- قیچی کاغذ را می‌برد  
- کاغذ سنگ را می‌پوشاند

🔫 **رولت روسی**
- 6 خانه، 1 گلوله
- نوبتی شلیک کنید
- اگر گلوله بیاید باختید!

🎲 **بازی تاس**
- هر نفر تاس می‌اندازد
- عدد بالاتر برنده است

🪙 **شیر یا خط**
- سکه پرتاب می‌شود
- حدس بزنید شیر یا خط؟

👊 **گل یا پوچ**
- یک نفر گل را مخفی می‌کند
- دیگری باید حدس بزند در کدام دست است"""

        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_main", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, rules, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش قوانین: {e}")

async def show_user_stats(uid: str):
    """نمایش آمار کاربر"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        user = DB["users"][uid]
        
        win_rate = 0
        if user["total_games"] > 0:
            win_rate = (user["games_won"] / user["total_games"]) * 100
        
        stats = f"""📊 **آمار شما**

🎮 **کل بازی‌ها:** {user["total_games"]}
🏆 **برد:** {user["games_won"]}
😔 **باخت:** {user["games_lost"]}
📈 **درصد برد:** {win_rate:.1f}%

👤 **نام مستعار:** {user["nickname"]}"""

        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_main", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, stats, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش آمار کاربر: {e}")

async def handle_admin_panel(uid: str, password: str = None):
    """مدیریت پنل ادمین"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        user = DB["users"][uid]
        
        if password == ADMIN_PASSWORD:
            user["is_admin"] = True
            user["admin_state"] = "main"
            await send_admin_menu(uid)
            return True
        else:
            await safe_send_message(uid, "❌ رمز عبور اشتباه است!")
            return False
            
    except Exception as e:
        print(f"❌ خطا در پنل ادمین: {e}")
        return False

async def handle_ticket_submission(uid: str, message: str):
    """ثبت تیکت جدید"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        ticket = {
            "id": len(DB["tickets"]) + 1,
            "user_id": uid,
            "user_name": DB["users"][uid]["nickname"],
            "message": message[:500],  # محدود کردن طول پیام
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "admin_reply": None
        }
        
        DB["tickets"].append(ticket)
        safe_save_tickets()
        
        await safe_send_message(
            uid, 
            f"✅ تیکت شما با شماره #{ticket['id']} ثبت شد.\n"
            f"به زودی پاسخ داده خواهد شد."
        )
        
    except Exception as e:
        print(f"❌ خطا در ثبت تیکت: {e}")

async def show_admin_stats(uid: str):
    """نمایش آمار ربات برای ادمین"""
    try:
        total_users = len(DB["users"])
        online_users = get_online_count()
        active_rooms = len(DB["rooms"])
        total_tickets = len(DB["tickets"])
        open_tickets = len([t for t in DB["tickets"] if t["status"] == "open"])
        total_games = DB["stats"]["total_games_played"]
        
        # آمار بازی‌ها
        games_stats = ""
        for game_type, count in DB["stats"]["games_by_type"].items():
            games_stats += f"   {game_type}: {count}\n"
        
        stats = f"""📊 **آمار کامل ربات**

👤 **کل کاربران:** {total_users}
🟢 **آنلاین:** {online_users}
🏠 **اتاق‌های فعال:** {active_rooms}
🎫 **کل تیکت‌ها:** {total_tickets}
📋 **تیکت‌های باز:** {open_tickets}
🎮 **کل بازی‌ها:** {total_games}

**آمار بازی‌ها:**
{games_stats if games_stats else "   هیچ بازی ثبت نشده"}"""

        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_admin", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, stats, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش آمار ادمین: {e}")

async def show_users_list(uid: str):
    """نمایش لیست کاربران"""
    try:
        users_text = "👥 **لیست کاربران:**\n\n"
        
        users_items = list(DB["users"].items())[:20]  # فقط 20 کاربر اول
        
        for user_id, user_data in users_items:
            status_emoji = {
                "idle": "⚪",
                "searching": "🔍", 
                "in_room": "🏠",
                "in_game": "🎮"
            }.get(user_data.get("status", "idle"), "⚪")
            
            users_text += (f"{status_emoji} **{user_data.get('nickname', 'بی‌نام')}**\n"
                          f"   🆔 `{user_id[-8:]}`\n"  # فقط 8 رقم آخر
                          f"   🏆 {user_data.get('games_won', 0)} برد\n\n")
        
        if len(DB["users"]) > 20:
            users_text += f"... و {len(DB['users']) - 20} کاربر دیگر"
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="back_to_admin", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, users_text, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش لیست کاربران: {e}")

async def show_tickets(uid: str):
    """نمایش تیکت‌ها"""
    try:
        if not DB["tickets"]:
            tickets_text = "📭 هیچ تیکتی وجود ندارد."
        else:
            tickets_text = "🎫 **تیکت‌های اخیر:**\n\n"
            
            # آخرین 10 تیکت
            recent_tickets = DB["tickets"][-10:]
            
            for ticket in reversed(recent_tickets):
                status_emoji = "🟢" if ticket["status"] == "open" else "🔴"
                message_preview = ticket['message'][:50] + "..." if len(ticket['message']) > 50 else ticket['message']
                created_date = ticket['created_at'][:10] if ticket.get('created_at') else 'نامشخص'
                tickets_text += (f"{status_emoji} **تیکت #{ticket['id']}**\n"
                               f"👤 {ticket.get('user_name', 'نامشخص')}\n"
                               f"💬 {message_preview}\n"
                               f"📅 {created_date}\n\n")
        
        builder = ChatKeypadBuilder()
        builder.row(builder.button(id="reply_tickets", text="📝 پاسخ تیکت"))
        builder.row(builder.button(id="back_to_admin", text=BTN_BACK))
        keypad = builder.build(resize_keyboard=True)
        
        await safe_send_message(uid, tickets_text, keypad)
        
    except Exception as e:
        print(f"❌ خطا در نمایش تیکت‌ها: {e}")

# تابع پردازش دکمه‌ها
async def handle_button_press(uid: str, button_id: str):
    """پردازش فشردن دکمه‌ها"""
    try:
        if uid not in DB["users"]:
            DB["users"][uid] = create_user_data()
        
        user = DB["users"][uid]
        
        # دکمه‌های منوی اصلی
        if button_id == "random_opponent":
            await start_random_search(uid)
        elif button_id == "create_room":
            await create_room(uid)
        elif button_id == "join_room":
            user["admin_state"] = "awaiting_room_code"
            await safe_send_message(uid, "🔢 کد 5 رقمی اتاق را وارد کنید:")
        elif button_id == "game_rules":
            await show_game_rules(uid)
        elif button_id == "my_stats":
            await show_user_stats(uid)
        elif button_id == "submit_ticket":
            user["admin_state"] = "awaiting_ticket"
            await safe_send_message(uid, "✍️ پیام خود را برای پشتیبانی بنویسید:")
        
        # دکمه‌های بازی
        elif button_id == "rps":
            await start_rock_paper_scissors(uid)
        elif button_id == "roulette":
            await start_russian_roulette(uid)
        elif button_id == "dice":
            await start_dice_game(uid)
        elif button_id == "heads_tails":
            await start_heads_tails(uid)
        elif button_id == "flower_money":
            await start_flower_money(uid)
        
        # دکمه‌های کنترل بازی
        elif button_id == "exit_game":
            await exit_game(uid)
        elif button_id == "leave_room":
            await leave_room(uid)
        elif button_id == "game_selection":
            await send_game_selection_menu(uid)
        
        # دکمه‌های بازگشت
        elif button_id == "back_to_main":
            if user.get("is_admin"):
                user["is_admin"] = False
                user["admin_state"] = "none"
            await send_main_menu(uid)
        elif button_id == "back_to_admin":
            if user.get("is_admin"):
                await send_admin_menu(uid)
        
        # دکمه‌های ادمین
        elif button_id == "admin_broadcast" and user.get("is_admin"):
            user["admin_state"] = "awaiting_broadcast"
            await safe_send_message(uid, "📝 پیام همگانی خود را بنویسید:")
        elif button_id == "admin_stats" and user.get("is_admin"):
            await show_admin_stats(uid)
        elif button_id == "admin_users" and user.get("is_admin"):
            await show_users_list(uid)
        elif button_id == "admin_tickets" and user.get("is_admin"):
            await show_tickets(uid)
        elif button_id == "reply_tickets" and user.get("is_admin"):
            await handle_reply_ticket_request(uid)
        
        # دکمه‌های جستجو
        elif button_id == "cancel_search":
            if uid in DB["waiting_queue"]:
                DB["waiting_queue"].remove(uid)
            user["status"] = "idle"
            await send_main_menu(uid, "❌ جستجو لغو شد.")
        
        # دکمه‌های بازی مجدد
        elif button_id == "rematch_yes":
            await handle_rematch_request(uid, True)
        elif button_id == "rematch_no":
            await handle_rematch_request(uid, False)
        
        # دکمه‌های بازی‌های خاص
        elif button_id in ["rock", "paper", "scissors"]:
            choice_map = {"rock": "rock", "paper": "paper", "scissors": "scissors"}
            await handle_rps_choice(uid, choice_map[button_id])
        elif button_id == "pull_trigger":
            await handle_russian_roulette(uid)
        elif button_id == "roll_dice":
            await handle_dice_game(uid)
        elif button_id in ["heads", "tails"]:
            await handle_heads_tails(uid, button_id)
        elif button_id in ["left_hand", "right_hand", "guess_left", "guess_right"]:
            await handle_flower_money(uid, button_id)
        
        safe_save_db()
        
    except Exception as e:
        print(f"❌ خطا در پردازش دکمه {button_id} برای {uid}: {e}")

async def handle_reply_ticket_request(uid: str):
    """پردازش درخواست پاسخ تیکت"""
    try:
        open_tickets = [t for t in DB["tickets"] if t["status"] == "open"]
        if open_tickets:
            user = DB["users"][uid]
            user["admin_state"] = "awaiting_ticket_reply"
            latest_ticket = open_tickets[-1]
            await safe_send_message(
                uid, 
                f"📝 **پاسخ تیکت #{latest_ticket['id']}:**\n\n"
                f"👤 کاربر: {latest_ticket.get('user_name', 'نامشخص')}\n"
                f"💬 پیام: {latest_ticket['message']}\n\n"
                f"پاسخ خود را بنویسید:"
            )
        else:
            await safe_send_message(uid, "❌ تیکت بازی برای پاسخ وجود ندارد!")
    except Exception as e:
        print(f"❌ خطا در پردازش درخواست پاسخ تیکت: {e}")

async def handle_rematch_request(uid: str, wants_rematch: bool):
    """پردازش درخواست بازی مجدد"""
    try:
        if uid not in DB["users"]:
            return
        
        user = DB["users"][uid]
        opponent = user.get("current_opponent")
        
        if not opponent or opponent not in DB["users"]:
            await send_main_menu(uid)
            return
        
        if wants_rematch:
            # بازگشت به منوی انتخاب بازی
            for player_id in [uid, opponent]:
                if player_id in DB["users"]:
                    DB["users"][player_id]["status"] = "in_room"
                    DB["users"][player_id]["current_game"] = None
                    DB["users"][player_id]["game_state"] = {}
            
            await send_game_selection_menu(uid, "🎯 بازی جدید انتخاب کنید:")
            await send_game_selection_menu(opponent, "🎯 بازی جدید انتخاب کنید:")
        else:
            await exit_game(uid)
            
    except Exception as e:
        print(f"❌ خطا در پردازش بازی مجدد: {e}")

@bot.on_message()
async def message_handler(bot: Robot, msg: Message):
    uid = str(msg.chat_id)
    text = msg.text.strip() if msg.text else ""
    
    try:
        # ثبت کاربر جدید
        if uid not in DB["users"]:
            try:
                tg_name = await bot.get_name(msg.chat_id)
                DB["users"][uid] = create_user_data()
                DB["users"][uid]["tg_name"] = tg_name or "کاربر"
                DB["users"][uid]["nickname"] = tg_name or "کاربر"
                DB["stats"]["total_users"] += 1
            except Exception as e:
                print(f"خطا در دریافت نام کاربر {uid}: {e}")
                DB["users"][uid] = create_user_data()
                DB["users"][uid]["tg_name"] = "کاربر"
                DB["users"][uid]["nickname"] = "کاربر"
            
            safe_save_db()
            print(f"کاربر جدید: {uid}")
        
        update_activity(uid)
        user = DB["users"][uid]
        
        # دستور خروج اضطراری
        if text == "/exit":
            user["status"] = "idle"
            user["current_game"] = None
            user["current_room"] = None
            user["current_opponent"] = None
            user["game_state"] = {}
            user["admin_state"] = "none"
            user["is_admin"] = False
            
            # حذف از صف‌ها
            if uid in DB["waiting_queue"]:
                DB["waiting_queue"].remove(uid)
            
            # اطلاع به حریف
            if user.get("current_opponent"):
                opponent = user["current_opponent"]
                if opponent in DB["users"]:
                    await safe_send_message(opponent, "❌ حریف از ربات خارج شد.")
                    await send_main_menu(opponent)
            
            await send_main_menu(uid, "🏠 به منوی اصلی بازگشتید.")
            safe_save_db()
            return
        
        # دستورات اصلی
        if text == "/start":
            user["status"] = "idle"
            user["admin_state"] = "none"
            user["is_admin"] = False
            await send_main_menu(uid, """🎮 به ربات بازی خوش آمدید!

لطفا جهت حمایت از ما در کانال ما عضو شوید👇
@python_source5

برای شروع یکی از گزینه‌های زیر را انتخاب کنید:""")
            return
        
        if text == "/help":
            help_text = """🎮 **راهنمای ربات بازی**

**دستورات:**
/start - شروع ربات
/exit - بازگشت به منوی اصلی (هرجا که باشید)
/help - راهنما
/admin - ورود به پنل مدیریت

**قابلیت‌ها:**
🎲 حریف شانسی - پیدا کردن حریف تصادفی
🏠 ساخت اتاق - ایجاد اتاق با کد 5 رقمی
🔑 ورود به اتاق - ورود با کد اتاق
📚 معرفی بازی‌ها - آشنایی با قوانین
🎫 ثبت تیکت - ارسال پیام به پشتیبانی

**بازی‌ها:**
✂️ سنگ کاغذ قیچی
🔫 رولت روسی
🎲 بازی تاس
🪙 شیر یا خط
👊 گل یا پوچ

اگر در جایی گیر کردید از دستور /exit استفاده کنید"""
            
            await msg.reply(help_text)
            return
        
        # پردازش پنل ادمین
        if text == "/admin":
            user["admin_state"] = "awaiting_password"
            await safe_send_message(uid, "🔐 رمز عبور پنل مدیریت را وارد کنید:")
            return
        
        if user["admin_state"] == "awaiting_password":
            success = await handle_admin_panel(uid, text)
            if not success:
                user["admin_state"] = "none"
            return
        
        # پردازش دستورات ادمین
        if user.get("is_admin") and user["admin_state"] in ["awaiting_broadcast", "awaiting_ticket_reply"]:
            
            if user["admin_state"] == "awaiting_broadcast":
                # ارسال پیام همگانی
                user["admin_state"] = "main"
                success = 0
                failed = 0
                
                for target_uid in list(DB["users"].keys()):
                    try:
                        await safe_send_message(target_uid, f"📢 **پیام مدیریت:**\n\n{text}")
                        success += 1
                        await asyncio.sleep(0.1)  # جلوگیری از spam
                    except:
                        failed += 1
                
                await safe_send_message(uid, f"✅ پیام به {success} کاربر ارسال شد.\n❌ {failed} خطا")
                await send_admin_menu(uid)
                safe_save_db()
                return
            
            elif user["admin_state"] == "awaiting_ticket_reply":
                # پاسخ به تیکت
                user["admin_state"] = "main"
                
                # پیدا کردن آخرین تیکت باز
                open_tickets = [t for t in DB["tickets"] if t["status"] == "open"]
                if open_tickets:
                    ticket = open_tickets[-1]  # آخرین تیکت
                    ticket["status"] = "closed"
                    ticket["admin_reply"] = text
                    
                    # ارسال پاسخ به کاربر
                    try:
                        await safe_send_message(
                            ticket["user_id"],
                            f"📨 **پاسخ تیکت #{ticket['id']}:**\n\n{text}\n\n---\n💬 پیام شما: {ticket['message']}"
                        )
                        await safe_send_message(uid, f"✅ پاسخ تیکت #{ticket['id']} ارسال شد.")
                    except:
                        await safe_send_message(uid, f"❌ خطا در ارسال پاسخ تیکت #{ticket['id']}")
                else:
                    await safe_send_message(uid, "❌ تیکت بازی یافت نشد!")
                
                safe_save_tickets()
                await send_admin_menu(uid)
                return
        
        # پردازش ثبت تیکت
        if user.get("admin_state") == "awaiting_ticket":
            user["admin_state"] = "none"
            await handle_ticket_submission(uid, text)
            await send_main_menu(uid)
            safe_save_db()
            return
        
        # پردازش ورود به اتاق
        if user.get("admin_state") == "awaiting_room_code":
            user["admin_state"] = "none"
            await join_room(uid, text.strip())
            safe_save_db()
            return
        
        # پردازش پیام‌های معمولی در بازی
        current_game = user.get("current_game")
        
        # پیام‌های چت حین بازی
        if user["status"] == "in_game" and user.get("current_opponent") and len(text) > 0 and not text.startswith('/'):
            opponent = user["current_opponent"]
            if opponent in DB["users"]:
                opponent_user = DB["users"][opponent]
                
                if opponent_user.get("status") == "in_game":
                    user_name = user["nickname"]
                    await safe_send_message(opponent, f"💬 **{user_name}:** {text}")
                    await safe_send_message(uid, "✅ پیام ارسال شد.")
            return
        # تعریف دکمه‌ها
# اضافه کردن به دیکشنری دکمه‌ها
        # پردازش دکمه‌ها با متن (حذف تیکت)
        button_map = {
            BTN_RANDOM_OPPONENT: "random_opponent",
            BTN_CREATE_ROOM: "create_room", 
            BTN_JOIN_ROOM: "join_room",
            BTN_GAME_RULES: "game_rules",
            BTN_MY_STATS: "my_stats",
            BTN_ROCK_PAPER_SCISSORS: "rps",
            BTN_RUSSIAN_ROULETTE: "roulette",
            BTN_DICE_GAME: "dice",
            BTN_HEADS_TAILS: "heads_tails",
            BTN_FLOWER_OR_MONEY: "flower_money",
            BTN_EXIT_GAME: "exit_game",
            BTN_BACK: "back_to_main",
            BTN_SUBMIT_TICKET: "submit_ticket",
            "❌ لغو جستجو": "cancel_search",
            "✅ بازی دوباره": "rematch_yes",
            "❌ خیر": "rematch_no",
            "🎯 انتخاب بازی": "game_selection",
            "🚪 ترک اتاق": "leave_room",
            # دکمه‌های بازی
            "🗿 سنگ": "rock",
            "📄 کاغذ": "paper", 
            "✂️ قیچی": "scissors",
            "🔫 شلیک": "pull_trigger",
            "🎲 انداختن تاس": "roll_dice",
            "🦁 شیر": "heads",
            "➖ خط": "tails",
            "👊 دست چپ": "left_hand",
            "👊 دست راست": "right_hand",
            # دکمه‌های ادمین (حذف تیکت)
            BTN_ADMIN_BROADCAST: "admin_broadcast",
            BTN_ADMIN_STATS: "admin_stats",
            BTN_ADMIN_USERS: "admin_users",
            "🔙 بازگشت به ادمین": "back_to_admin"
        }
        
        if text in button_map:
            await handle_button_press(uid, button_map[text])
        else:
            # پیام نامشخص
            if user["status"] == "idle":
                await safe_send_message(uid, "❓ دستور نامشخص. از /help برای راهنما استفاده کنید.")
        
        safe_save_db()
        
    except Exception as e:
        print(f"❌ خطای کلی در پردازش پیام {uid}: {e}")
        try:
            await safe_send_message(uid, "❌ خطایی رخ داد. لطفاً مجدداً تلاش کنید.")
        except:
            pass

async def periodic_cleanup():
    """پاکسازی دوره‌ای"""
    while True:
        try:
            await asyncio.sleep(300)  # هر 5 دقیقه
            cleanup_inactive_users()
            
            # پاکسازی اتاق‌های خالی
            empty_rooms = []
            for room_code, room_data in DB["rooms"].items():
                if len(room_data.get("players", [])) == 0:
                    empty_rooms.append(room_code)
            
            for room_code in empty_rooms:
                del DB["rooms"][room_code]
            
            if empty_rooms:
                print(f"🧹 {len(empty_rooms)} اتاق خالی پاکسازی شد")
            
            # ذخیره دوره‌ای
            if len(DB["users"]) > 0:
                safe_save_db()
                
        except Exception as e:
            print(f"❌ خطا در پاکسازی دوره‌ای: {e}")

async def main():
    """اجرای اصلی ربات"""
    try:
        print("🔄 بارگذاری پایگاه داده...")
        safe_load_db()
        
        print("⚙️ تنظیم دستورات...")
        await set_com()
        
        print("🧹 شروع پاکسازی دوره‌ای...")
        # شروع پاکسازی دوره‌ای در پس‌زمینه
        asyncio.create_task(periodic_cleanup())
        
        print("🎮 ربات بازی در حال اجرا...")
        print("📊 آمار اولیه:")
        print(f"   👤 تعداد کاربران: {len(DB['users'])}")
        print(f"   🎮 کل بازی‌ها: {DB['stats']['total_games_played']}")
        
        await bot.run()
        
    except KeyboardInterrupt:
        print("\n🛑 خروج از ربات...")
    except Exception as e:
        print(f"❌ خطای کلی: {e}")
    finally:
        print("💾 ذخیره نهایی اطلاعات...")
        safe_save_db()
        print("✅ اطلاعات ذخیره شد.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 خداحافظ!")
    except Exception as e:
        print(f"❌ خطای اجرا: {e}")
    finally:
        # ذخیره اضطراری
        try:
            safe_save_db()
        except:
            pass
