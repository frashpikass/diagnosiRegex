from pickle import dumps, loads
from base64 import b64encode, b64decode
import xml.etree as ET

class Marca():
    def __init__(self, nome, valore_marchio):
        self.nome = nome
        self.valore_marchio = valore_marchio

    def __repr__(self):
        return f"{self.nome} ({self.valore_marchio}€)"

class Macchina():
    def __init__(self, nome, ruote, valori, marca: Marca):
        self.nome = nome
        self.ruote = ruote
        self.valori = valori
        self.marca = marca

    def __repr__(self):
        return f"{self.marca} {self.nome}: {self.ruote} ruote, valori {self.valori}"


marca_1 = Marca("Fiat", "1000")
marca_2 = Marca("Audi", "10000")

m1 = Macchina("500",4,[1,2,3],marca_1)
m2 = Macchina("A4",4,[6,7,8,9],marca_2)
m3 = Macchina("A5",4,[7,7,8,9],marca_2)

lista_macchine=[m1,m2,m3]

pickledb64 = b64encode(dumps(lista_macchine))
unpickled = loads(b64decode(pickledb64))

# Test di pickling
for m in unpickled:
    print(m)

print(unpickled)
print(unpickled[1].marca is unpickled[2].marca)
print(unpickled[2].marca)