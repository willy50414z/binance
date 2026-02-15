import configparser
import os

parser = configparser.ConfigParser()
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', 'config', 'config.ini')
config_path = os.path.normpath(config_path)
parser.read(config_path)


def get(section="DEFAULT", option=""):
    return parser.get(section, option)


class config_util:
    def __init__(self, section):
        self.section = section

    def get(self, option):
        return get(self.section, option)
