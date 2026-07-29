import oracledb

connection = oracledb.connect(
    user="AR_ADMIN",
    password="Annuminnu@27",
    host="localhost",
    port=1521,
    service_name="FREEPDB1"
)

cursor = connection.cursor()
cursor.execute("SELECT USER, SYSDATE FROM dual")

row = cursor.fetchone()

print("Connected successfully!")
print("Connected user:", row[0])
print("Database date:", row[1])

cursor.close()
connection.close()