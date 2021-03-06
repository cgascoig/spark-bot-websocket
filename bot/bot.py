#!/usr/bin/env python

"""


"""

from flask import Flask, request
from ciscosparkapi import CiscoSparkAPI
import os
import sys
import json
import websocket
import thread
import html2text

# Create the Flask application that provides the bot foundation
app = Flask(__name__)

sessions_by_room_id = {}
sessions_by_ws = {}

class Session():
	def __init__(self, room_id):
		self.room_id = room_id
		self.ws = None
		self.thread = None
		self.cmdid = 0
		sessions_by_room_id[room_id] = self
	
	def connect_ws(self):
		self.ws = websocket.WebSocketApp("ws://localhost:8002/?%s"%self.room_id,
			on_message = on_ws_message,
			on_error = on_ws_error,
			on_close = on_ws_close)
		self.ws.on_open = on_ws_open

		sessions_by_ws[self.ws] = self

		self.thread = thread.start_new_thread(self.ws.run_forever, ())

	def send_ws(self, message):
		if self.ws is None:
			self.connect_ws()

		self.ws.send(message)
		
	def get_cmdid(self):
		self.cmdid=self.cmdid+1
		return self.cmdid


@app.route('/', methods=['POST'])
def process_webhook():
	post_data = request.get_json(force=True)
	sys.stderr.write("Webhook content:" + "\n")
	sys.stderr.write(str(post_data) + "\n")

	room_id = post_data["data"]["roomId"]
	message_id = post_data["data"]["id"]
	message = spark.messages.get(message_id)
	sys.stderr.write("Message content: %s\n"%str(message))

	# Ignore my own messages
	if message.personEmail in spark.people.me().emails:
		return ""
	
	sys.stderr.write("Message from: " + message.personEmail + "\n")

	try:
		session = sessions_by_room_id[room_id]
	except:
		session = Session(room_id)
		if session is None:
			sys.stderr.write("ERROR: Failed to create session")
			return ""

	session.send_ws("[\"text\", [\"%s\"], {\"cmdid\": %d}]"%(message.text, session.get_cmdid()))

	return ""

# Function to Setup the WebHook for the bot
def setup_webhook(name, targeturl):
	# Get a list of current webhooks
	webhooks = spark.webhooks.list()

	# Look for a Webhook for this bot_name
	# Need try block because if there are NO webhooks it throws an error
	try:
		for h in webhooks:  # Efficiently iterates through returned objects
			if h.name == name:
				sys.stderr.write("Found existing webhook.  Updating it.\n")
				wh = spark.webhooks.update(webhookId=h.id, name=name, targetUrl=targeturl)
				# Stop searching
				break

		# If there wasn't a Webhook found
		if wh is None:
			sys.stderr.write("Creating new webhook.\n")
			wh = spark.webhooks.create(name=name, targetUrl=targeturl, resource="messages", event="created")
	except:
		sys.stderr.write("Creating new webhook.\n")
		wh = spark.webhooks.create(name=name, targetUrl=targeturl, resource="messages", event="created")

	return wh

def spark_setup(email, token):
	# Setup the Spark Connection
	globals()["spark"] = CiscoSparkAPI(access_token=globals()["spark_token"])
	globals()["webhook"] = setup_webhook(globals()["bot_app_name"], globals()["bot_url"])
	sys.stderr.write("Configuring Webhook. \n")
	sys.stderr.write("Webhook ID: " + globals()["webhook"].id + "\n")


def on_ws_message(ws, message):
	msg = json.loads(message)
	sys.stderr.write("\n\nReceived websocket message: CMD: '%s', Args: %s, KWArgs: %s\n\n"%(msg[0], str(msg[1]), str(msg[2])))
	
	try:
		session = sessions_by_ws[ws]
	except:
		sys.stderr.write("ERROR: Failed to find session for websocket!!!\n")

	spark.messages.create(roomId=session.room_id, markdown="```\n%s\n```" % html2text.html2text(msg[1][0]))

def on_ws_error(ws, error):
	sys.stderr.write("WebSocket Error: %s\n"%error)

def on_ws_open(ws):
	sys.stderr.write("WebSocket Opened\n")

def on_ws_close(ws):
	sys.stderr.write("WebSocket Closed\n")

if __name__ == '__main__':
	# setup websocket backend connection
	websocket.enableTrace(True)
#	ws = websocket.WebSocketApp("ws://localhost:8002/?eswcgcpqharrgw1mmodrerx1mxmu4m8n",
#		on_message = on_ws_message,
#		on_error = on_ws_error,
#		on_close = on_ws_close)
#	ws.on_open = on_ws_open
#	ws_thread = thread.start_new_thread(ws.run_forever, ())
#	# ws.run_forever()

	bot_email = os.getenv("SPARK_BOT_EMAIL")
	spark_token = os.getenv("SPARK_BOT_TOKEN")
	bot_url = os.getenv("SPARK_BOT_URL")
	bot_app_name = os.getenv("SPARK_BOT_APP_NAME")

	spark = None
	webhook = None

	if spark_token is None or bot_email is None:
		sys.stderr.write("Configuration missing")
	else:
		spark_setup(bot_email, spark_token)

	app.run(debug=True, host='0.0.0.0', port=5000)