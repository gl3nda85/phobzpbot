# always make explicit includes
from peewee import Model, PrimaryKeyField, CharField, DateTimeField, IntegerField, ForeignKeyField,datetime
from database.db import BaseModel
from database.User import User

class UserSocial(BaseModel):
    id = PrimaryKeyField()
    social_id = IntegerField()
    social_name = CharField()
    social_username = CharField()
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    user = ForeignKeyField(User, backref='usersocials')