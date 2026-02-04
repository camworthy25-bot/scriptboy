print("SCRIPT STARTED")
import discord
from discord.ext import commands
import random, json, time, os

TOKEN = os.getenv("DISCORD_TOKEN")  # Use environment variable in Railway!
PREFIX = ","

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

DATA_FILE = "data.json"

START_COINS = 1000
DAILY_COINS = 500
MAX_BET = 5000
BET_COOLDOWN = 8

XP_COOLDOWN = 30  # seconds between XP gains
BASE_XP = 1000    # level 1 requirement

# create json file if missing
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load():
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def key(gid, uid):
    return f"{gid}-{uid}"

def xp_needed(level):
    return int(BASE_XP * (level * (level + 1) / 2))

def get_user(data, gid, uid):
    k = key(gid, uid)
    if k not in data:
        data[k] = {
            "coins": START_COINS,
            "last_bet": 0,
            "last_daily": 0,
            "xp": 0,
            "level": 1,
            "last_xp": 0
        }
    return data[k]

@bot.event
async def on_ready():
    print(f"Online as {bot.user}")

# ---------- XP SYSTEM ----------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    data = load()
    user = get_user(data, message.guild.id, message.author.id)
    now = time.time()

    if now - user["last_xp"] >= XP_COOLDOWN:
        user["last_xp"] = now
        user["xp"] += random.randint(15, 30)

        needed = xp_needed(user["level"])
        if user["xp"] >= needed:
            user["level"] += 1
            reward = user["level"] * 1000
            user["coins"] += reward
            await message.channel.send(
                f"🎉 {message.author.mention} leveled up to **Level {user['level']}**!\n"
                f"💰 Reward: **{reward} coins**"
            )

    save(data)
    await bot.process_commands(message)

# ---------- STATS ----------
@bot.command()
async def stats(ctx):
    data = load()
    u = get_user(data, ctx.guild.id, ctx.author.id)
    await ctx.send(
        f"📊 **Stats for {ctx.author.name}**\n"
        f"Level: **{u['level']}**\n"
        f"XP: **{u['xp']} / {xp_needed(u['level'])}**\n"
        f"Coins: **{u['coins']}**"
    )

# ---------- DAILY ----------
@bot.command()
async def daily(ctx):
    data = load()
    user = get_user(data, ctx.guild.id, ctx.author.id)
    now = time.time()

    if now - user["last_daily"] < 86400:
        await ctx.send("🕒 Already claimed.")
        return

    user["last_daily"] = now
    user["coins"] += DAILY_COINS
    save(data)
    await ctx.send(f"🧧 You got **{DAILY_COINS} coins**")

# -----------------------------
# GAMBLING COMMANDS
# -----------------------------
GAMBLE_COOLDOWN = 8  # seconds

# COIN FLIP / BET
@bot.command()
async def bet(ctx, amount: int):
    data = load()  # Load data first
    user = get_user(data, ctx.guild.id, ctx.author.id)
    now = time.time()

    if now - user["last_bet"] < GAMBLE_COOLDOWN:
        await ctx.send("⏳ Cooldown.")
        return

    if amount <= 0 or amount > user["coins"] or amount > MAX_BET:
        await ctx.send("❌ Invalid bet.")
        return

    user["last_bet"] = now
    if random.choice([True, False]):
        user["coins"] += amount
        result = f"🎉 You WON **{amount} coins**!"
    else:
        user["coins"] -= amount
        result = f"💥 You LOST **{amount} coins**!"

    save(data)  # Fixed: save the data variable instead of save(load())
    await ctx.send(result)

# -----------------------------
# PRAY / LUCK COMMAND
# -----------------------------
@bot.command()
async def pray(ctx):
    """Pray for luck! Small chance for coins or XP."""
    data = load()
    user = get_user(data, ctx.guild.id, ctx.author.id)
    reward_type = random.choice(["coins", "xp", "nothing"])
    
    if reward_type == "coins":
        amount = random.randint(50, 300)
        user["coins"] += amount
        msg = f"🙏 The gods smiled upon you! You received **{amount} coins**!"
    elif reward_type == "xp":
        amount = random.randint(20, 100)
        user["xp"] += amount
        msg = f"🙏 The gods blessed your knowledge! You gained **{amount} XP**!"
    else:
        msg = f"😔 The gods ignored your prayer this time. Better luck next time!"

    save(data)
    await ctx.send(msg)

# ---------- MONEY ----------
@bot.command()
async def money(ctx):
    """Check your coin balance"""
    data = load()
    user = get_user(data, ctx.guild.id, ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, you have **{user['coins']} coins**")

# SLOTS
@bot.command()
async def slots(ctx, amount: int):
    data = load()
    user = get_user(data, ctx.guild.id, ctx.author.id)

    if amount <= 0 or amount > user["coins"]:
        await ctx.send("❌ Invalid bet.")
        return

    reels = ["🍒", "🍋", "🍉", "⭐", "💎"]
    spin = [random.choice(reels) for _ in range(3)]

    if len(set(spin)) == 1:  # jackpot
        win = amount * 3
        user["coins"] += win
        result = f"🎰 {' '.join(spin)}\n**JACKPOT! You win {win} coins!**"
    else:
        user["coins"] -= amount
        result = f"🎰 {' '.join(spin)}\n**You lost {amount} coins.**"

    save(data)
    await ctx.send(result)

class BlackjackView(discord.ui.View):
    def __init__(self, author, guild_id, bet, player, dealer):
        super().__init__(timeout=60)
        self.author = author
        self.guild_id = guild_id
        self.bet = bet
        self.player = player
        self.dealer = dealer

    async def interaction_check(self, interaction):
        return interaction.user == self.author

    async def finish(self, interaction):
        while hand_value(self.dealer) < 17:
            self.dealer.append(draw_card())

        p = hand_value(self.player)
        d = hand_value(self.dealer)

        data = load()
        user = get_user(data, self.guild_id, self.author.id)

        if p > 21:
            result = "💥 Bust! You lost."
            user["coins"] -= self.bet
        elif d > 21 or p > d:
            result = "🎉 You win!"
            user["coins"] += self.bet
        elif p == d:
            result = "😐 Push (tie)"
        else:
            result = "💀 Dealer wins."
            user["coins"] -= self.bet

        save(data)
        self.clear_items()

        await interaction.response.edit_message(
            content=(
                f"🃏 **Blackjack**\n\n"
                f"Your hand: `{self.player}` = **{p}**\n"
                f"Dealer: `{self.dealer}` = **{d}**\n\n"
                f"{result}"
            ),
            view=self
        )

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction, button):
        self.player.append(draw_card())
        if hand_value(self.player) >= 21:
            await self.finish(interaction)
        else:
            await interaction.response.edit_message(
                content=(
                    f"🃏 **Blackjack**\n\n"
                    f"Your hand: `{self.player}` = **{hand_value(self.player)}**\n"
                    f"Dealer: `{self.dealer[0]}`, ?"
                ),
                view=self
            )

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction, button):
        await self.finish(interaction)


# Run the bot
bot.run(TOKEN)