# always make explicit includes
from peewee import Model, PrimaryKeyField, CharField, DateTimeField, IntegerField, ForeignKeyField
from database.db import BaseModel
from database.User import User

class CoinInfo(BaseModel):
    id = PrimaryKeyField()
    photon_balance = IntegerField()
    photon_address = CharField()
    blake_balance = IntegerField()
    blake_address = CharField()
    user = ForeignKeyField(User, backref='Coininfos')