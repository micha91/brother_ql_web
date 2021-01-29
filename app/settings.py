import json

DEBUG = False
CONFIG = None


def init():
    global DEBUG, CONFIG

    try:
        with open('app-config/config.json', encoding='utf-8') as fh:
            CONFIG = json.load(fh)
    except FileNotFoundError as e:
        with open('app-config/config.example.json', encoding='utf-8') as fh:
            CONFIG = json.load(fh)
