## channel.py - a simple message channel
##

from flask import Flask, request, render_template, jsonify
import re
import json
import requests

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

MAXIMUM_MESSAGES = 5

# Language learning specific constants
SUPPORTED_LANGUAGES = ['english', 'spanish', 'french', 'german']
LANGUAGE_PATTERNS = {
    'hello': {'spanish': '¡Hola!', 'french': 'Bonjour!', 'german': 'Hallo!'},
    'goodbye': {'spanish': '¡Adiós!', 'french': 'Au revoir!', 'german': 'Auf Wiedersehen!'},
    'thanks': {'spanish': '¡Gracias!', 'french': 'Merci!', 'german': 'Danke!'},
    'please': {'spanish': 'por favor', 'french': 'sʼil vous plaît', 'german': 'bitte'},
    'yes': {'spanish': 'sí', 'french': 'oui', 'german': 'ja'},
    'no': {'spanish': 'no', 'french': 'non', 'german': 'nein'}
}

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

    response = check_for_request(message['content'])
    print("rep", response)

    messages.append({'content': message['content'],
                     'sender': message['sender'],
                     'timestamp': message['timestamp'],
                     'extra': extra,
                     })
    save_messages(messages)

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
        return [{"content": "Hi, this a language learning channel! We hope you have fun! Just type: Translate German hello", "sender": "Welcome", "timestamp": "2025-02-17T16:37:03.057091", "extra": None}]
    try:
        messages = json.load(f)
    except json.decoder.JSONDecodeError:
        messages = []
    f.close()

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
    for profane in PROFANITY_WORDS:
        if (message['content'].lower().find(profane) >= 0):
            message['content'] = "There has been a forbidden word, please remember to choose your language carefully ..."
            message['sender'] = "BotModerator"
    return message

def check_for_request(message):
    lower_case = message.lower()

    tokens = re.sub(r'[^\w\s]', '', lower_case).split(' ')
    print(tokens)

    new_content = ""

    try:
        tokens.remove('translate')

        for lang in SUPPORTED_LANGUAGES:
            try:

                tokens.remove(lang)

                # TODO Give message to tell someone to input a word as well
                if len(tokens) == 0: 
                    return

                for token in tokens:
                    if token in LANGUAGE_PATTERNS:
                        translation = LANGUAGE_PATTERNS[token][lang]
                        new_content = new_content + ("%s is %s in %s!   " % (token.title(), translation, lang.title()))
                    else:
                        new_content = new_content + ("Sorry, for this word, %s, we don't have a translation in %s.    \n" % (token, lang.title()))

            except:
                continue

        if len(new_content) == 0:
            return "Please remember to give a language to translate to ..."
        else:
            return new_content
        
    except:
        return None



# Start development web server
# run flask --app channel.py register
# to register channel with hub

if __name__ == '__main__':
    app.run(port=5001, debug=True)
