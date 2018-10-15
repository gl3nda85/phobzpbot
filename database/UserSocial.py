# always make explicit includes
from peewee import Model, PrimaryKeyField, CharField, DateTimeField, IntegerField, ForeignKeyField
from database.db import BaseModel
from database.User import User

class UserSocial(BaseModel):
    id = PrimaryKeyField()
    social_id = IntegerField()
    social_name = CharField()
    social_username = CharField()
    user = ForeignKeyField(User, backref='usersocials')