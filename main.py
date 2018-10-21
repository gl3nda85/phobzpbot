from telegram.ext import Updater, CommandHandler
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from datetime import datetime, timedelta
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

rpc_providers = {}


rpc_providers['PHO'] = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['photon_rpc']['user'], config['photon_rpc']['password'],
							config['photon_rpc']['host'], config['photon_rpc']['port']))
rpc_providers['BLC'] = AuthServiceProxy("http://%s:%s@%s:%d" %
						   (config['blake_rpc']['user'], config['blake_rpc']['password'],
							config['blake_rpc']['host'], config['blake_rpc']['port']))

tickers = ['PHO', 'BLC']

logging.basicConfig(
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	level=logging.INFO)

def check_auth(email, password):
	user = get_user_from_email(email)

	return sha256_crypt.verify(password, user.password)

def get_social_user_from_id(social_id):
	try:
		social_user = UserSocial.get((UserSocial.social_name == 'telegram') & (UserSocial.social_id == social_id))
		return social_user
	except Exception as e:
		print(e)
		return None

def get_social_user_from_username(username):
	clean_username = username[1:]
	try:
		return UserSocial.select().where((UserSocial.social_name == 'telegram') & (UserSocial.social_username == clean_username)).first()
	except Exception as e:
		print(e)
		return None
	
def get_user_from_email(email):
	try:
		return User.select().where(User.email == email).first()
	except Exception as e:
		return None
	
def find_user_by_id(id):
	try:
		return User.get_by_id(id)
	except Exception as e:
		print(e)
		return None

def get_coininfo_from_user(user):
	try:
		return CoinInfo.select().where(CoinInfo.user_id == user.id).get()
	except Exception as e:
		print(e)
		return None

def is_registered(email):

	# query the database to see if the telegram id is registered with any user


	# if the telegram id is found return true

	return User.select().where(User.email == email).get() is not None

def is_registered_id(social_id):

	try:
		return get_social_user_from_id(social_id) is not None
	except Exception as e:
		return False

def update_active_user(social_user):
	social_user.updated_at = datetime.now()
	return social_user.save() > 1

def give_balance(social_id, amount, ticker):

	social_user = get_social_user_from_id(social_id)
	found_user = find_user_by_id(social_user.user_id)
	coin_info = get_coininfo_from_user(found_user)

	if ticker == "PHO":
		coin_info.photon_balance = coin_info.photon_balance - amount
	else:
		coin_info.blake_balance = coin_info.blake_balance - amount

	coin_info.save()

	return social_user

def get_balance(social_id, ticker):

	rpc = rpc_providers[ticker.upper()]

	social_user = get_social_user_from_id(social_id)
	found_user = find_user_by_id(social_user.user_id)
	coin_info = get_coininfo_from_user(found_user)
	balance = None

	print(tickers)
	address = get_address(found_user, ticker)
	print(address)
	received = rpc.getreceivedbyaddress(address)
	print(received)

	if ticker == "PHO":
		balance = coin_info.photon_balance
	else:
		balance = coin_info.blake_balance

	return received - Decimal(balance)

def get_unconfirmed(social_user, ticker):

	rpc = rpc_providers[ticker.upper()]

	address = get_address(find_user_by_id(social_user.user_id), ticker)

	received = rpc.getreceivedbyaddress(address)

	received_unconfirmed = rpc.getreceivedbyaddress(address, 0)

	return received_unconfirmed - received

def validate_address(address, ticker):
	return rpc_providers[ticker.upper()].validateaddress(address)['isvalid']

def generate_address(ticker):
	return rpc_providers[ticker.upper()].getnewaddress()

def get_address(user, ticker):
	coininfo = None
	ticker = ticker.upper()
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

def generate_coin_info(user):
	address_set = CoinInfo(photon_balance=0, blake_balance=0,photon_address=generate_address("PHO"), blake_address=generate_address("BLC"), user=user)
	saved = address_set.save()
	return saved

def start(bot, update):
	update.message.reply_text('Hello! I\'m a tipbot for the Blakezone Portal ' +
							  'Add me to a group and start tipping!')

	# add_to_chat(get_social_user_from_id(update.message.from_user.id), update.message.chat_id)

def tip(bot, update):
	args = update.message.text.split()[1:]

	if len(args) == 3:
		user = get_social_user_from_username(args[0])
		from_user = get_social_user_from_id(update.message.from_user.id)
		ticker = args[1].upper()
		try:
			amount = Decimal(args[2])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /tip <ticker> <user> <amount>")
			return

		if user is not None and from_user is not None:
			if amount > 0:
				if get_balance(update.message.from_user.id, ticker) - amount >= 0:

					from_user = give_balance(update.message.from_user.id, -amount, ticker)
					user = give_balance(user.social_id, amount, ticker)

					bot.sendMessage(chat_id=update.message.chat_id,
									text="%s tipped %s %s %f" % (
										from_user.social_username,
										user.social_username,
										ticker,
										amount
									))
					update_active_user(from_user)
					update_active_user(user)
				else:
					update.message.reply_text("Not enough money!")
			else:
				update.message.reply_text("Invalid amount!")
		else:
			update.message.reply_text("%s is not registered!" % (args[0]))
	else:
		update.message.reply_text("Usage: /tip <user> <ticker> <amount>")

def soak(bot, update):
	args = update.message.text.split()[1:]

	if len(args) == 2:
		from_user = get_social_user_from_id(update.message.from_user.id)
		ticker = args[0].upper()
		try:
			amount = Decimal(args[1])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /soak <ticker> <amount>")
			return

		if amount > 0:
			if get_balance(from_user.social_id, ticker) - amount >= 0:

				# grab most active users that have interated with the bot
				last_hour_date_time = datetime.now() - timedelta(hours = 1)
				users = (UserSocial.select().where((UserSocial.updated_at >= last_hour_date_time) & (UserSocial.social_id != from_user.social_id)))
				result_length = len(list(users))
				if result_length > 0:
					tip = amount/result_length
					from_user = give_balance(from_user.social_id, -amount, ticker)

					usernames = []

					for user in users:
						pprint(user)
						give_balance(user.social_id, tip, ticker)
						update_active_user(user)
						usernames.append(str("@") + user.social_username)

					users_str = ", ".join(usernames)

					update_active_user(from_user)
					bot.sendMessage(chat_id=update.message.chat_id,
									text="%s soaked %s %f to %s!" % (
										from_user.social_username,
										ticker,
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
		update.message.reply_text("Usage: /soak <ticker> <amount>")

	# add_to_chat(get_user_from_email(update.message.from_user.id), update.message.chat_id)

def balance(bot, update):
	ticker_keys =	{
	  "PHO": 175,
	  "BLC": 125
	}

	args = update.message.text.split()[1:]

	if len(args) == 1:
		args[0] = args[0].upper()
		if args[0] in tickers:

			quote_page = requests.get('https://api.coinmarketcap.com/v2/ticker/'+ str(ticker_keys[args[0]])+'/?convert=ltc')
			jsonResult = quote_page.json()
			data = jsonResult['data']
			ltcPrice = float(data['quotes']['LTC']['price'])
			usdPrice = float(data['quotes']['USD']['price'])
			social_user_id = update.message.from_user.id
			social_user_username = update.message.from_user.username
			social_user = get_social_user_from_id(social_user_id)
			if social_user is None:
				bot.send_message(chat_id=update.message.chat_id, text="You havent registered your telegram account to blakezone!")
			else:
				result  = get_balance(social_user_id, args[0])
				balance  = float(result)
				fiat_balance = balance * usdPrice
				fiat_balance = str(round(fiat_balance,3))
				ltc_balance = balance * ltcPrice
				ltc_balance = str(round(ltc_balance,3))
				balance =  str(round(balance,3))
				unconfirmed = ""

				update_active_user(social_user)
				if get_unconfirmed(social_user, args[0]) > 0:
					unconfirmed = "(+ %s unconfirmed)" % \
								  get_unconfirmed(social_user, args[0])

				bot.send_message(chat_id=update.message.chat_id, text="@{0} your current balance is: {1} {2} ≈ ${3} or {4} LTC {5}".format(social_user_username, args[0], balance,fiat_balance, ltc_balance, unconfirmed))
		else:
			update.message.reply_text("ticker not found")

	else:
		update.message.reply_text("Usage: /balance <ticker>")

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
				user = get_user_from_email(email)
				social_user = UserSocial(social_id=update.message.from_user.id, social_name= 'telegram', social_username=update.message.from_user.username, user=user)
				social_saved = social_user.save()  # save() returns the number of rows modified.
				coininfo_saved = generate_coin_info(user)
				if social_saved > 0 and coininfo_saved > 0:
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

	update_active_user(social_user)

def deposit(bot, update):
	args = update.message.text.split()[1:]
	social_user = get_social_user_from_id(update.message.from_user.id)
	if len(args) == 1:
		ticker = args[0].upper()
		if ticker in tickers:
			update.message.reply_text("Your deposit address is %s" % get_address(find_user_by_id(social_user.user_id), ticker))
		else:
			update.message.reply_text("something went wrong!")
	else:
		update.message.reply_text("Usage: /deposit <ticker>")
	update_active_user(social_user)

def withdraw(bot, update):

	args = update.message.text.split()[1:]

	if len(args) == 3:
		try:
			amount = Decimal(args[2])
		except decimal.InvalidOperation:
			update.message.reply_text("Usage: /withdraw <address> <ticker> <amount>")
			return
		bal = get_balance(update.message.from_user.id, args[1])
		ticker = args[1].upper()
		if bal - amount >= 0 and amount > 1:
			if validate_address(args[0], args[1]):

				rpc = rpc_providers[ticker]

				rpc.settxfee(0.5)
				txid = rpc.sendtoaddress(args[0], amount - 1)

				social_user = get_social_user_from_id(update.message.from_user.id)
				give_balance(social_user.social_id, -amount, args[1])
				update_active_user(social_user)
				update.message.reply_text(
					"Withdrew %f %s! TX: %s" %
					(amount-1,ticker, "https://chainz.cryptoid.info/pho/tx.dws?" + str(txid)))
			else:
				update.message.reply_text("Invalid address")
		else:
			update.message.reply_text("amount has to be more than 1, and " +
									  "you need to have enough RPI Coins")
	else:
		update.message.reply_text("Usage: /withdraw <address> <ticker> <amount>")

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

	# add_to_chat(get_user_from_email(update.message.from_user.id), update.message.chat_id)

def contribute(bot, update):
	   bot.send_message(chat_id=update.message.chat_id, text='Thanks for your interest in contributing!\n\n'
                                                          'This project is run as a labour of love, but if you would like to help '
                                                          'feel free to tip the bot:\n\n'
                                                          '/tip @PhotonTipBot <amount> \n\n'
                                                          'or contribute directly to:\n\n'
                                                          '{0} \n\n'
                                                          'Thanks for using the Photon Tipbot!'.format(conf.contribution_address))

def getBlockExplorerBalance(bot, update):
	target = update.message.text[8:]
	address = target[:35]
	url = "https://chainz.cryptoid.info/pho/api.dws?q=getbalance&a={0}".format(address)
	balance_result = requests.get(url)
	balance = balance_result.text
	bot.send_message(chat_id=update.message.chat_id, text="The current balance for the address {0} is {1} PHO" .format(address, balance))


def commands(bot, update):
	user = update.message.from_user.username 
	bot.send_message(chat_id=update.message.chat_id, text="Initiating commands /tip & /withdraw have a specfic format,\n use them like so:" + "\n \n Parameters: \n <user> = target user to tip \n <amount> = amount of Photon to utilise \n <address> = Photon address to withdraw to \n \n Tipping format: \n /tip <user> <amount> \n \n Withdrawing format: \n /withdraw <address> <amount>")

def help(bot, update):
	bot.send_message(chat_id=update.message.chat_id, text="The following commands are at your disposal: /hi , /commands , /deposit , /tip , /withdraw , /price , /expbal,  /contribute , /marketcap or /bal")


def price(bot,update):
	quote_page = requests.get('https://api.coinmarketcap.com/v2/ticker/175/?convert=ltc')
	jsonResult = quote_page.json()
	data = jsonResult['data']
	ltcPriceChange = data['quotes']['LTC']['percent_change_1h']
	ltcPrice = float(data['quotes']['LTC']['price'])
	usdPrice = float(data['quotes']['USD']['price'])
	bot.send_message(chat_id=update.message.chat_id, text="Photon is valued at {0} LTC and {1} USD Δ %{2}".format(ltcPrice, usdPrice, ltcPriceChange))


def marketcap(bot,update):
	quote_page = requests.get('https://api.coinmarketcap.com/v2/ticker/175/?convert=ltc')
	jsonResult = quote_page.json()
	data = jsonResult['data']

	ltcMarketCap = data['quotes']['LTC']['market_cap']
	usdMarketCap = data['quotes']['USD']['market_cap']
	bot.send_message(chat_id=update.message.chat_id, text="The current market cap of Photon is valued at {0} LTC and ${1} USD" .format(ltcMarketCap, usdMarketCap))

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
	updater.dispatcher.add_handler(CommandHandler('market', marketcap))
	updater.dispatcher.add_handler(CommandHandler('soak', soak))
	updater.dispatcher.add_handler(CommandHandler('help', help))
	updater.dispatcher.add_handler(CommandHandler('contribute', contribute))
	updater.dispatcher.add_handler(CommandHandler('expbal', getBlockExplorerBalance))
	updater.dispatcher.add_handler(CommandHandler('commands', commands))
	updater.start_polling()
	updater.idle()
