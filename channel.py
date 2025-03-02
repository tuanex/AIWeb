## channel.py - a simple message channel
##

from flask import Flask, request, render_template, jsonify
import re
import json
import requests
import deepl

# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """

    # Flask settings
    SECRET_KEY = 'This is an INSECURE secret!! DO NOT use this in production!!' # change to something random, no matter what

# Create Flask app
app = Flask(__name__)
app.config.from_object(__name__ + '.ConfigClass')  # configuration
app.app_context().push()  # create an app context before initializing db

HUB_URL = 'http://localhost:5555'
HUB_AUTHKEY = '1234567890'
CHANNEL_AUTHKEY = '0987654321'
CHANNEL_NAME = "Language Learning Chat"
CHANNEL_ENDPOINT = "http://localhost:5001" # don't forget to adjust in the bottom of the file
CHANNEL_FILE = 'messages.json'
CHANNEL_TYPE_OF_SERVICE = 'aiweb24:chat'

MAXIMUM_MESSAGES = 50

# Language to consider
LANGUAGES = {
    'english': 'EN',
    'german': 'DE',
    'spanish': 'ES',
    'swedish': 'SV',
    'french': 'FR'
}
# Authkey for DeepL API
DEEPL_AUTHKEY = "91b66d38-aed4-4f18-987f-09b27203f3bc:fx"

# Remove profanity_check import and replace with simple word list
PROFANITY_WORDS = {
    'fuck', 'shit', 'ass', 'bitch', 'damn'  # Add more words as needed
}

@app.cli.command('register')
def register_command():
    global CHANNEL_AUTHKEY, CHANNEL_NAME, CHANNEL_ENDPOINT, CHANNEL_FILE

    # send a POST request to server /channels
    response = requests.post(
            HUB_URL + '/channels', 
            headers={'Authorization': 'authkey ' + HUB_AUTHKEY},
            data=json.dumps({
               "name": CHANNEL_NAME,
               "endpoint": CHANNEL_ENDPOINT,
               "authkey": CHANNEL_AUTHKEY,
               "type_of_service": CHANNEL_TYPE_OF_SERVICE,
            })
    )

    if response.status_code != 200:
        print("Error creating channel: "+str(response.status_code))
        print(response.text)
        return

def check_authorization(request):
    global CHANNEL_AUTHKEY
    # check if Authorization header is present
    if 'Authorization' not in request.headers:
        return False
    # check if authorization header is valid
    if request.headers['Authorization'] != 'authkey ' + CHANNEL_AUTHKEY:
        return False
    return True

@app.route('/health', methods=['GET'])
def health_check():
    global CHANNEL_NAME
    if not check_authorization(request):
        return "Invalid authorization", 400
    return jsonify({'name':CHANNEL_NAME}),  200

# GET: Return list of messages
@app.route('/', methods=['GET'])
def home_page():
    if not check_authorization(request):
        return "Invalid authorization", 400
    # fetch channels from server
    return jsonify(read_messages())

# POST: Send a message
@app.route('/', methods=['POST'])
def send_message():
    # fetch channels from server
    # check authorization header
    if not check_authorization(request):
        return "Invalid authorization", 400
    # check if message is present
    message = request.json
    if not message:
        return "No message", 400
    if not 'content' in message:
        return "No content", 400
    if not 'sender' in message:
        return "No sender", 400
    if not 'timestamp' in message:
        return "No timestamp", 400
    if not 'extra' in message:
        extra = None
    else:
        extra = message['extra']
    # add message to messages
    messages = read_messages()

    message = check_against_forbidden(message)

    # Return None if there was no request made, else append the returned string later
    response = check_for_request(message['content'])

    messages.append({'content': message['content'],
                     'sender': message['sender'],
                     'timestamp': message['timestamp'],
                     'extra': extra,
                     })
    save_messages(messages)

    # If there is a response, the is sent as well
    if response != None:
        print("rep", response)
        messages.append({'content': response,
                         'sender': "BotModerator",
                         'timestamp': message['timestamp'] + '1',
                         'extra': None})
        
        save_messages(messages)

    return "OK", 200

def read_messages():
    global CHANNEL_FILE
    try:
        f = open(CHANNEL_FILE, 'r')
    except FileNotFoundError:
        # Still prepend standard message, if there is no file
        return [{"content": "Hi, this a language learning channel! We hope you have fun! Just type: Translate \"Hello\" to German. Supported languages are: German, English, and Spanish.", "sender": "Welcome", "timestamp": "2025-02-17T16:37:03.057091", "extra": None}]
    try:
        messages = json.load(f)
    except json.decoder.JSONDecodeError:
        messages = []
    f.close()

    # Prepend standard message where necessary
    welcome_message = '[{"content": "Hi, this a language learning channel! We hope you have fun! Just type: Translate German hello", "sender": "Welcome", "timestamp": "2025-02-17T16:37:03.057091", "extra": null}]'

    if len(messages) == 0:
        if messages[0] != welcome_message:
            messages = [welcome_message] + messages
    return messages

def save_messages(messages):
    global CHANNEL_FILE, MAXIMUM_MSGS

    few_messages = messages[-(MAXIMUM_MESSAGES):]
    if (messages[0] != few_messages[0]):
        few_messages = [messages[0]] + few_messages

    with open(CHANNEL_FILE, 'w') as f:
        json.dump(few_messages, f)

def check_against_forbidden(message):
    # Check against forbidden words
    for profane in PROFANITY_WORDS:
        if (message['content'].lower().find(profane) >= 0):
            message['content'] = "There has been a forbidden word, please remember to choose your language carefully ..."
            message['sender'] = "BotModerator"
    return message

# Make the http request to get the translation 
def get_translation(text, lang):
    translator = deepl.Translator(DEEPL_AUTHKEY)

    result = translator.translate_text(text, target_lang=lang)
    return result

# Parse the message and find the language and words to translate (to)
def check_for_request(message):
    # Lower to make easier to analyse
    message_lower = message.lower()

    # Check if request before further analysis
    message_request = message_lower.replace("translate", "")
    if message_lower == message_request:
        print("no translate")
        return
    else:
        print("Do translate")

    # Make analysis easier
    message_no_punc = re.sub(r'[^a-zA-Z0-9" ]', '', message_request)
    # Find string to translate
    target_string = re.search(r'".+"', message_no_punc).group()
    # Remove target string to make search for target lang easier
    message_no_str = message_no_punc.replace(target_string, "")

    # Make search for lang easier
    tokens = message_no_str.split(' ')

    target_language = None

    # Scan for only the 1st language code
    for token in tokens:
        if token in LANGUAGES:
            if target_language == None:
                target_language = token
                break

    if target_language == None:
        return "Please remember to add a language to translate to."
    
    response = get_translation(target_string[1:-1], LANGUAGES[target_language])

    return "The requested phrase, " + target_string + ", is \"" + response.text + "\", in " + target_language.title() + "."
    



# Start development web server
# run flask --app channel.py register
# to register channel with hub

if __name__ == '__main__':
    app.run(port=5001, debug=True)
