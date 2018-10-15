import datetime
from peewee import *
import json
config = json.loads(open("config.json").read())

db = MySQLDatabase(
	host=config['mysql']['host'],
	user=config['mysql']['user'],
	password=config['mysql']['password'],
	database=config['mysql']['db']
)

class BaseModel(Model):
    class Meta:
        database = db