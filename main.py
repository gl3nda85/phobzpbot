from telegram.ext import Updater, CommandHandler
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from decimal import Decimal
import requests
import logging
import json
from database.db import db
from database.User import User
from database.UserSocial import UserSocial
from database.CoinInfo import CoinInfo
from pprint import pprint
from passlib.apps import custom_app_context as pwd_context
from passlib.hash import sha256_crypt 

config = json.loads(open("config.json").read())

photon_rpc = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['photon_rpc']['user'], config['photon_rpc']['password'],
							config['photon_rpc']['host'], config['photon_rpc']['port']))
blake_rpc = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['blake_rpc']['user'], config['blake_rpc']['password'],
							config['blake_rpc']['host'], config['blake_rpc']['port']))

tickers = ['PHO', 'BLC']

logging.basicConfig(
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	level=logging.INFO)


def get_mysql():
	return db

def check_auth(email, password):
	user = get_user(email)

	return sha256_crypt.verify(password, user.password)

def get_user_id(user):

	social_user = UserSocial.select().where((UserSocial.social_name == 'telegram') & (UserSocial.social_id == user)).get()
	found_user = User.get(User.id == social_user.user_id)
	return found_user


def get_user(email):
	return User.select().where(User.email == email).get()


def add_to_chat(user, chat):
	db = get_mysql()

	db.users.update({'userid': user['userid']}, {'$addToSet': {'chats': chat}})


def is_registered(email):

	# query the database to see if the telegram id is registered with any user


	# if the telegram id is found return true

	return User.select().where(User.email == email).get() is not None


def is_registered_id(user):

	try:
		return UserSocial.select().where((UserSocial.social_name == 'telegram') & (UserSocial.social_id == user)).get() != 0
	except Exception as e:
		return False


def give_balance(user, amount, ticker):

	social_user = UserSocial.select().where((UserSocial.social_name == 'telegram') & (UserSocial.social_id == user))
	found_user = User.select().where(User.id == UserSocial.user_id)
	coin_info = CoinInfo.select().where(CoinInfo.user_id == found_user.id)

	db.users.update({'userid': user['userid']},
					{'$inc': {'redeemed': float(-amount)}})

	return db.users.find_one({'userid': user['userid']})


def get_balance(user):
	db = get_mysql()

	rpc = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['rpc']['user'], config['rpc']['password'],
							config['rpc']['host'], config['rpc']['port']))
	address = get_address(user)

	received = rpc.getreceivedbyaddress(address)

	return received - Decimal(db.users.find_one(
								{'userid': user['userid']}).get('redeemed', 0))


def get_unconfirmed(user):
	rpc = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['rpc']['user'], config['rpc']['password'],
							config['rpc']['host'], config['rpc']['port']))
	address = get_address(user)

	received = rpc.getreceivedbyaddress(address)
	received_unconfirmed = rpc.getreceivedbyaddress(address, 0)

	return received_unconfirmed - received


def validate_address(address):
	rpc = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['rpc']['user'], config['rpc']['password'],
							config['rpc']['host'], config['rpc']['port']))
	return rpc.validateaddress(address)['isvalid']

def generate_address(ticker):

	if ticker == 'PHO':
		return photon_rpc.getnewaddress()
	else:
		return blake_rpc.getnewaddress()

def get_address(user, ticker):
	coininfo = None
	#see if deposit info exists for user.
	try:
		coininfo = CoinInfo.get(CoinInfo.user_id == user.id)
	except Exception as e:
		print(e)
	
	if coininfo is None:
		address_set = CoinInfo(photon_balance=0, blake_balance=0,photon_address=generate_address("PHO"), blake_address=generate_address("BLC"), user=user)
		saved = address_set.save()
		if saved > 0:
			if ticker == "PHO":
				return address_set.photon_address
			else:
				return address_set.blake_address
	else:
		if ticker == "PHO":
			return coininfo.photon_address
		else:
			return coininfo.blake_address


def start(bot, update):
	update.message.reply_text('Hello! I\'m a tipbot for the Blakezone Portal ' +
							  'Add me to a group and start tipping! userid: ' + str(update.message.from_user.id))

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def tip(bot, update):
	args = update.message.text.split()[1:]

	if len(args) == 3:
		# Unfortunatelly the only way i can currently think of for getting the
		# user ID for the username is if I get the user to register first.
		# Sucks, but I guess I need it to be done

		user = get_user_id(args[1])
		from_user = get_user(update.message.from_user.id)
		ticker


		try:
			amount = Decimal(args[2])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /tip <ticker> <user> <amount>")
			return

		if user is not None and from_user is not None:
			if amount > 0:
				if get_balance(from_user) - amount >= 0:

					from_user = give_balance(from_user, -amount, )
					user = give_balance(user, amount)

					bot.sendMessage(chat_id=update.message.chat_id,
									text="%s tipped %s %f RPI" % (
										from_user['username'],
										args[0],
										amount
									))
				else:
					update.message.reply_text("Not enough money!")
			else:
				update.message.reply_text("Invalid amount!")
		else:
			update.message.reply_text("%s is not registered!" % (args[0]))
	else:
		update.message.reply_text("Usage: /tip <ticker> <user> <amount>")

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def soak(bot, update):
	args = update.message.text.split()[1:]

	if len(args) == 1:
		from_user = get_user(update.message.from_user.id)
		try:
			amount = Decimal(args[0])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /soak <amount>")
			return

		if amount > 0:
			if get_balance(from_user) - amount >= 0:
				db = get_mysql()

				users = db.users.find({'chats': update.message.chat_id,
									   'userid': {'$ne': from_user['userid']},
									   'username': {'$ne': None}})

				if users.count() > 0:
					tip = amount/users.count()
					from_user = give_balance(from_user, -amount)

					usernames = []

					for user in users:
						print(user)
						give_balance(user, tip)
						usernames.append(user['username'])

					users_str = ", ".join(usernames)

					print(users.count())

					for user in users:
						print(user)
						give_balance(user, tip)

					bot.sendMessage(chat_id=update.message.chat_id,
									text="%s soaked %f RPI to %s!" % (
										from_user['username'],
										tip,
										users_str
									))
				else:
					update.message.reply_text("No users on this channel have"
											  " interacted with the bot.")
			else:
				update.message.reply_text("Not enough money!")
		else:
			update.message.reply_text("Invalid amount")
	else:
		update.message.reply_text("Usage: /soak <amount>")

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def balance(bot, update):
	bal = get_balance(get_user(update.message.from_user.id))

	r = requests.get('https://api.cryptonator.com/api/ticker/%s-%s' %
					 ('ok', 'usd'))
	usd = Decimal(bal)*Decimal(r.json()['ticker']['price'])

	unconfirmed = ""

	if get_unconfirmed(get_user(update.message.from_user.id)) > 0:
		unconfirmed = "(+ %s unconfirmed)" % \
					  get_unconfirmed(get_user(update.message.from_user.id))

	update.message.reply_text("You have %s RPI (%f USD) %s" %
							  (bal, usd, unconfirmed))

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


# this register function is now complient with photon
def register(bot, update):
	args = update.message.text.split()[1:]

	if len(args) == 2:
		email = args[0]
		password = args[1]

		#check if someone already owns this telegram id

		if not is_registered_id(update.message.from_user.id):

			#if no one owns the telegram id, authenticate the user against the DB
			#and link their blake zone account

			if not is_registered(email):
				update.message.reply_text("Please register at https://blakezone.com!")
			try:
				check_auth(email, password)
				user = get_user(email)
				social_user = UserSocial(social_id=update.message.from_user.id, social_name= 'telegram', social_username=update.message.from_user.username, user=user)
				saved = social_user.save()  # save() returns the number of rows modified.
				if saved > 0:
					update.message.reply_text("This telegram account with username %s and user id %d \n has been connected to the blakezone account with email %s" % (update.message.from_user.username, update.message.from_user.id, user.email))
				else:
					update.message.reply_text("This telegram account is already connected to a blakezone account")
			except Exception as e:
				print(e)
				update.message.reply_text("Your blakezone username or password is incorrect!")
		else:
			update.message.reply_text("This telegram account is already connected to a blakezone account")
	else:
		update.message.reply_text("Usage: /register <email> <password> \n Register is used to connect your telegram account to your blakezone account!")

	# add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def deposit(bot, update):

	args = update.message.text.split()[1:]

	if len(args) == 1:
		if args[0] in tickers:
				update.message.reply_text("Your deposit address is %s" % get_address(get_user_id(update.message.from_user.id), args[0]))
	else:
		update.message.reply_text("Usage: /deposit <ticker>")

	# add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def withdraw(bot, update):
	bal = get_balance(get_user(update.message.from_user.id))

	args = update.message.text.split()[1:]

	if len(args) == 2:
		try:
			amount = Decimal(args[1])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /withdraw <address> <amount>")
			return
		if bal - amount >= 0 and amount > 1:
			if validate_address(args[0]):
				rpc = AuthServiceProxy("http://%s:%s@%s:%d" %
									   (config['rpc']['user'],
										config['rpc']['password'],
										config['rpc']['host'],
										config['rpc']['port']))
				rpc.settxfee(0.5)
				txid = rpc.sendtoaddress(args[0], amount-1)
				give_balance(get_user(update.message.from_user.id), -amount)
				update.message.reply_text(
					"Withdrew %f RPI! TX: %s" %
					(amount-1, "https://explorer.rpicoin.com/tx/" + txid))
			else:
				update.message.reply_text("Invalid address")
		else:
			update.message.reply_text("amount has to be more than 1, and " +
									  "you need to have enough RPI Coins")
	else:
		update.message.reply_text("Usage: /withdraw <address> <amount>")

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def convert(bot, update):
	args = update.message.text.split()[1:]

	if len(args) == 3:
		try:
			amount = Decimal(args[0])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /convert <amount> <from> <to>")
			return

		request = requests.get('https://api.cryptonator.com/api/ticker/%s-%s' %
							   (args[1], args[2]))

		ticker = request.json()

		if ticker['success']:
			res = Decimal(ticker['ticker']['price']) * amount
			base = ticker['ticker']['base']
			target = ticker['ticker']['target']
			update.message.reply_text("%f %s = %f %s" % (amount, base, res,
									  target))
		else:
			update.message.reply_text("Error: %s " % ticker['error'])

	else:
		update.message.reply_text("Usage: /convert <amount> <from> <to>")

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


def market(bot, update):
	args = update.message.text.split()[1:]

	if len(args) > 0:
		base = args[0]
		if len(args) > 1:
			target = args[1]
		else:
			target = 'usd'
	else:
		base = 'ok'
		target = 'btc'

	request = requests.get('https://api.cryptonator.com/api/full/%s-%s' %
						   (base, target))

	ticker = request.json()

	if ticker['success']:
		price = Decimal(ticker['ticker']['price'])
		volume = ticker['ticker']['volume']
		change = ticker['ticker']['change']
		markets = ticker['ticker']['markets']

		message = "Price: %s Volume: %s Change: %s\n" % (price, volume, change)

		for market in markets:
			name = market['market']
			price = market['price']
			volume = market['volume']
			message += "\n%s - Price: %s Volume: %s" % (name, price, volume)

		update.message.reply_text(message)
	else:
		update.message.reply_text("Error: %s " % ticker['error'])

	add_to_chat(get_user(update.message.from_user.id), update.message.chat_id)


if __name__ == "__main__":
	db.create_tables([User, UserSocial, CoinInfo])
	updater = Updater(config['token'])

	updater.dispatcher.add_handler(CommandHandler('start', start))
	updater.dispatcher.add_handler(CommandHandler('tip', tip))
	updater.dispatcher.add_handler(CommandHandler('register', register))
	updater.dispatcher.add_handler(CommandHandler('balance', balance))
	updater.dispatcher.add_handler(CommandHandler('bal', balance))
	updater.dispatcher.add_handler(CommandHandler('deposit', deposit))
	updater.dispatcher.add_handler(CommandHandler('withdraw', withdraw))
	updater.dispatcher.add_handler(CommandHandler('convert', convert))
	updater.dispatcher.add_handler(CommandHandler('con', convert))
	updater.dispatcher.add_handler(CommandHandler('market', market))
	updater.dispatcher.add_handler(CommandHandler('soak', soak))

	updater.start_polling()
	updater.idle()
