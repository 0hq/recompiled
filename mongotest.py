from pymongo import MongoClient
# pprint library is used to make the output look more pretty
from pprint import pprint
# connect to MongoDB, change the << MONGODB URL >> to reflect your own connection string
client = MongoClient("mongodb+srv://server:Pfi88XLO8TrqSgqY@cluster0.ztv48.mongodb.net/Main?retryWrites=true&w=majority")
# db = client["Writers"]
# Issue the serverStatus command and print the results
# serverStatusResult=db.command("serverStatus")
test = client.Main.Writers.find()
# print(test)
for r in test:
    print(r)