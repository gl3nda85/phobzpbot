# always make explicit includes
from peewee import Model, PrimaryKeyField, CharField, DateTimeField, datetime
from database.db import BaseModel


class User(BaseModel):
    id = PrimaryKeyField()
    email = CharField(unique=True)
    nickname = CharField()
    password = CharField()
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)