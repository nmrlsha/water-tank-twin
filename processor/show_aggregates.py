from storage import Storage

db = Storage("data/tank.db")
for row in db.per_minute(10):
    print(row)
db.close()