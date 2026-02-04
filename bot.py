print("SCRIPT STARTED")
import discord
from discord import app_commands
from discord.ext import commands
import random, json, time, os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced")

bot = Bot()

DATA_FILE = "data.json"
START_COINS = 1000
DAILY_COINS = 500
MAX_BET = 5000
BET_COOLDOWN = 8
XP_COOLDOWN = 30
BASE_XP = 1000

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
    print(f"✅ Online as {bot.user}")

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

# ==================== SLASH COMMANDS ====================

@bot.tree.command(name="stats", description="View your stats and level")
async def stats(interaction: discord.Interaction):
    data = load()
    u = get_user(data, interaction.guild.id, interaction.user.id)
    
    embed = discord.Embed(title=f"📊 Stats for {interaction.user.name}", color=discord.Color.blue())
    embed.add_field(name="Level", value=f"**{u['level']}**", inline=True)
    embed.add_field(name="XP", value=f"**{u['xp']} / {xp_needed(u['level'])}**", inline=True)
    embed.add_field(name="Coins", value=f"**{u['coins']}** 💰", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily coins")
async def daily(interaction: discord.Interaction):
    data = load()
    user = get_user(data, interaction.guild.id, interaction.user.id)
    now = time.time()

    if now - user["last_daily"] < 86400:
        remaining = 86400 - (now - user["last_daily"])
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await interaction.response.send_message(f"🕒 Already claimed! Come back in {hours}h {minutes}m", ephemeral=True)
        return

    user["last_daily"] = now
    user["coins"] += DAILY_COINS
    save(data)
    await interaction.response.send_message(f"🧧 You claimed **{DAILY_COINS} coins**! 💰")

@bot.tree.command(name="money", description="Check your coin balance")
async def money(interaction: discord.Interaction):
    data = load()
    user = get_user(data, interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(f"💰 {interaction.user.mention}, you have **{user['coins']} coins**")

# ==================== BET BUTTONS ====================

class BetView(discord.ui.View):
    def __init__(self, user_id, guild_id, amount):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.guild_id = guild_id
        self.amount = amount
        self.used = False

    @discord.ui.button(label="🪙 Heads", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id or self.used:
            await interaction.response.send_message("Not your bet!", ephemeral=True)
            return
        
        self.used = True
        data = load()
        user = get_user(data, self.guild_id, self.user_id)
        
        result = random.choice(["heads", "tails"])
        won = result == "heads"
        
        if won:
            user["coins"] += self.amount
            msg = f"🎉 It's **HEADS**! You WON **{self.amount} coins**!"
        else:
            user["coins"] -= self.amount
            msg = f"💥 It's **TAILS**! You LOST **{self.amount} coins**!"
        
        save(data)
        await interaction.response.edit_message(content=msg, view=None)

    @discord.ui.button(label="🪙 Tails", style=discord.ButtonStyle.danger)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id or self.used:
            await interaction.response.send_message("Not your bet!", ephemeral=True)
            return
        
        self.used = True
        data = load()
        user = get_user(data, self.guild_id, self.user_id)
        
        result = random.choice(["heads", "tails"])
        won = result == "tails"
        
        if won:
            user["coins"] += self.amount
            msg = f"🎉 It's **TAILS**! You WON **{self.amount} coins**!"
        else:
            user["coins"] -= self.amount
            msg = f"💥 It's **HEADS**! You LOST **{self.amount} coins**!"
        
        save(data)
        await interaction.response.edit_message(content=msg, view=None)

@bot.tree.command(name="bet", description="Flip a coin - choose heads or tails!")
@app_commands.describe(amount="Amount of coins to bet")
async def bet(interaction: discord.Interaction, amount: int):
    data = load()
    user = get_user(data, interaction.guild.id, interaction.user.id)
    now = time.time()

    if now - user["last_bet"] < BET_COOLDOWN:
        await interaction.response.send_message("⏳ Cooldown active!", ephemeral=True)
        return

    if amount <= 0 or amount > user["coins"] or amount > MAX_BET:
        await interaction.response.send_message("❌ Invalid bet amount!", ephemeral=True)
        return

    user["last_bet"] = now
    save(data)
    
    view = BetView(interaction.user.id, interaction.guild.id, amount)
    await interaction.response.send_message(f"🪙 Choose **Heads** or **Tails**! Betting **{amount} coins**", view=view)

@bot.tree.command(name="pray", description="Pray for luck!")
async def pray(interaction: discord.Interaction):
    data = load()
    user = get_user(data, interaction.guild.id, interaction.user.id)
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
        msg = "😔 The gods ignored your prayer this time. Better luck next time!"

    save(data)
    await interaction.response.send_message(msg)

# ==================== SLOTS BUTTON ====================

class SlotsView(discord.ui.View):
    def __init__(self, user_id, guild_id, amount):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.guild_id = guild_id
        self.amount = amount

    @discord.ui.button(label="🎰 SPIN", style=discord.ButtonStyle.success, emoji="🎰")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        
        data = load()
        user = get_user(data, self.guild_id, self.user_id)
        
        if self.amount > user["coins"]:
            await interaction.response.send_message("❌ Not enough coins!", ephemeral=True)
            return

        reels = ["🍒", "🍋", "🍉", "⭐", "💎"]
        spin = [random.choice(reels) for _ in range(3)]

        if len(set(spin)) == 1:
            win = self.amount * 3
            user["coins"] += win
            result = f"🎰 {' '.join(spin)}\n\n✨ **JACKPOT! You win {win} coins!** ✨"
        else:
            user["coins"] -= self.amount
            result = f"🎰 {' '.join(spin)}\n\n💥 You lost {self.amount} coins."

        save(data)
        await interaction.response.edit_message(content=result, view=None)

@bot.tree.command(name="slots", description="Try your luck at the slot machine!")
@app_commands.describe(amount="Amount of coins to bet")
async def slots(interaction: discord.Interaction, amount: int):
    data = load()
    user = get_user(data, interaction.guild.id, interaction.user.id)

    if amount <= 0 or amount > user["coins"]:
        await interaction.response.send_message("❌ Invalid bet amount!", ephemeral=True)
        return

    view = SlotsView(interaction.user.id, interaction.guild.id, amount)
    await interaction.response.send_message(f"🎰 **Slot Machine** 🎰\nBetting: **{amount} coins**\n\nPress SPIN to play!", view=view)

# ==================== BLACKJACK ====================

def draw_card():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

def hand_value(hand):
    value = sum(hand)
    aces = hand.count(11)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

class BlackjackView(discord.ui.View):
    def __init__(self, user_id, guild_id, bet_amount, player_hand, dealer_hand):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet_amount = bet_amount
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.finished = False

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        if self.finished:
            await interaction.response.send_message("Game already finished!", ephemeral=True)
            return

        self.player_hand.append(draw_card())
        player_val = hand_value(self.player_hand)

        if player_val > 21:
            self.finished = True
            data = load()
            user = get_user(data, self.guild_id, self.user_id)
            user["coins"] -= self.bet_amount
            save(data)
            
            await interaction.response.edit_message(
                content=f"🃏 **Blackjack**\n\nYour hand: {self.player_hand} = **{player_val}**\n\n💥 **BUST! You lost {self.bet_amount} coins!**",
                view=None
            )
        else:
            await interaction.response.edit_message(
                content=f"🃏 **Blackjack**\n\nYour hand: {self.player_hand} = **{player_val}**\nDealer: [{self.dealer_hand[0]}, ?]",
                view=self
            )

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        if self.finished:
            await interaction.response.send_message("Game already finished!", ephemeral=True)
            return

        self.finished = True
        
        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(draw_card())

        player_val = hand_value(self.player_hand)
        dealer_val = hand_value(self.dealer_hand)

        data = load()
        user = get_user(data, self.guild_id, self.user_id)

        if dealer_val > 21 or player_val > dealer_val:
            user["coins"] += self.bet_amount
            result = f"🎉 **You WIN {self.bet_amount} coins!**"
        elif player_val < dealer_val:
            user["coins"] -= self.bet_amount
            result = f"💥 **Dealer wins! You lost {self.bet_amount} coins!**"
        else:
            result = "🤝 **Push! It's a tie.**"

        save(data)
        
        await interaction.response.edit_message(
            content=f"🃏 **Blackjack**\n\nYour hand: {self.player_hand} = **{player_val}**\nDealer: {self.dealer_hand} = **{dealer_val}**\n\n{result}",
            view=None
        )

@bot.tree.command(name="blackjack", description="Play blackjack against the dealer!")
@app_commands.describe(amount="Amount of coins to bet")
async def blackjack(interaction: discord.Interaction, amount: int):
    data = load()
    user = get_user(data, interaction.guild.id, interaction.user.id)

    if amount <= 0 or amount > user["coins"]:
        await interaction.response.send_message("❌ Invalid bet amount!", ephemeral=True)
        return

    player = [draw_card(), draw_card()]
    dealer = [draw_card(), draw_card()]

    view = BlackjackView(interaction.user.id, interaction.guild.id, amount, player, dealer)

    await interaction.response.send_message(
        f"🃏 **Blackjack**\n\nYour hand: {player} = **{hand_value(player)}**\nDealer: [{dealer[0]}, ?]",
        view=view
    )

# Run the bot
bot.run(TOKEN)