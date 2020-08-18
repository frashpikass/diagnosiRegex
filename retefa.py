"""
File di descrizione degli elementi della struttura dati in input.
"""
from typing import List
import xmlschema
import xml.etree as ET


## CLASSI ##

class Buffer(object):
    """
    Classe che descrive la relazione fra link ed eventi.
    """

    def __init__(self, link, evento: str):
        self.link = link
        self.evento = evento


class Transizione(object):
    """
    Classe che descrive la transizione fra due stati all'interno di un comportamento.
    La classe include la descrizione delle etichette di osservabilità e rilevanza.
    """

    def __init__(
            self,
            nome: str,
            stato0,
            stato1,
            eventoNecessario: Buffer,
            eventiOutput: List[Buffer],
            osservabilita="",
            rilevanza=""):
        self.nome = nome
        self.stato0 = stato0
        self.stato1 = stato1
        self.eventoNecessario = eventoNecessario
        self.eventiOutput = eventiOutput
        self.osservabilita = osservabilita
        self.rilevanza = rilevanza


class Stato(object):
    """
    Classe che descrive uno stato di un comportamento e le sue transizioni uscenti.
    """

    def __init__(self, nome: str, transizioniUscenti: List[Transizione] = None):
        self.nome = nome
        self.transizioniUscenti = transizioniUscenti

    def addTransizioneUscente(self, transizione: Transizione):
        """
        Aggiunge una transizione alle transizioni uscenti dallo stato
        :param transizione: la transizione da aggiungere
        """
        self.transizioniUscenti.append(transizione)


class Comportamento(object):
    """
    Classe che descrive un comportamento della rete FA, i suoi stati, le sue transizioni e lo stato iniziale.
    """

    def __init__(self, nome, stati: List[Stato] = None, transizioni: List[Transizione] = None, statoIniziale: Stato = None):
        self.nome = nome
        self.stati = stati
        self.transizioni = transizioni
        self.statoIniziale = statoIniziale

    def addStato(self, newStato: Stato):
        """
        Aggiunge lo stato dato agli stati di questo Comportamento
        :param newStato: il nuovo Stato da aggiungere
        :return: None
        """
        self.stati.append(newStato)

    def findStatoByNome(self, nomeStato: str) -> Stato:
        """
        Cerca uno Stato nel Comportamento a partire dal suo nome
        :param nomeStato: il nome dello Stato
        :return: se presente, lo Stato, None altrimenti
        """
        for stato in self.stati:
            if stato.nome == nomeStato:
                return stato
        return None


class Link(object):
    """
    Classe che descrive un link fra due comportamenti nella topologia della rete FA.
    """

    def __init__(self, nome, comportamento0: Comportamento, comportamento1: Comportamento):
        """
        Costruttore della classe Link
        :param nome: Nome del link
        :param comportamento0: comportamento iniziale
        :param comportamento1: comportamento terminale
        """

        self.nome = nome
        self.comportamento0 = comportamento0
        self.comportamento1 = comportamento1


class ReteFA:
    """
    Classe principale di questo file, descrive complessivamente una rete FA, i suoi comportamenti e i suoi link.
    """

    def __init__(self, nome: str, comportamenti: List[Comportamento] = None, links: List[Link] = None):
        """
        :type nome: String
        :type comportamenti: Comportamento[]
        :type links: Link[]
        """
        self.id = nome
        self.comportamenti = comportamenti
        self.links = links

    def validateXML(self, xml) -> bool:
        """
        Metodo per validare l'XML in input
        :return: true se l'XML è valido
        """
        # todo: porta fuori la costante/path
        xsdPath = 'D:\\STORAGE\\Dropbox\\Dropbox\\000 Specialistica\\ASD\\Progetto ASD 2020\\input.xsd'
        schema = xmlschema.XMLSchema(xsdPath)
        return schema.is_valid(xml)

    def fromXML(self, xml):
        """
        Costruisce la rete FA a partire dai dati contenuti nell'XML che la descrive
        :param xml: xml che descrive la rete FA
        :return: la reteFA costruita a partire dall'XML
        """

        out = None


        """
        Costruzione della struttura dati in ordine tale da verificare che i riferimenti incrociati fra elementi della struttura esistano
        Costruiamo gli oggetti nel seguente ordine. Segno con * dove fare il controllo degli errori:
            1- comportamenti, comportamento(nome)
            2- links(nome, comp0*, comp1*) *controlla che esistano i comportamenti
            3- comportamenti, comportamento, stati, stato(nome)
            4- statoIniziale* del comportamento *controlla che esista lo stato indicato
            5- transizioni, transizione(nome, stato0*, stato1*, osservabilita, rilevanza) *controlla che gli stati esistano
            6- eventualmente evento necessario della transizione eventoNecessario(nome, link*) *controlla che il link esista
            7- eventualmente eventiOutput(evento, link*) *controlla che il link esista
            
            8- compilazione delle transizioni uscenti
        """

        import xml.etree as ET

        # Validazione dell'XML
        if self.validateXML(xml):
            tree = ET.ElementTree.parse(source=xml)
            root = tree.getroot()

            # 0. Costruzione della rete, con l'attributo nome
            out = ReteFA(root.attrib['nome'])

            # 1. Costruzione dei comportamenti
            for comp in root.findall('comportamenti/comportamento'):
                newComp = Comportamento(comp.get('nome'))
                out.addComportamento(newComp)

            # 2. Costruzione dei links (con controllo dell'errore sull'esistenza dei comportamenti)
            for link in root.findall('links/link'):
                # Recupero degli attributi del link
                nome = link.attrib()['nome']
                comp0 = link.attrib()['comp0']
                comp1 = link.attrib()['comp1']
                # Agiungiamo il link descritto dagli attributi
                out.addLink(nome, comp0, comp1)

                newComp.addStato()

            # 3-4-5-6-7. Introduzione degli stati, dello stato iniziale e delle
            # transizioni (con etichette) nei comportamenti
            for comp in root.findall('comportamenti/comportamento'):
                nomeComp = comp.attrib()['nome']
                # Cerco il comportamento comp nella rete
                comportamento = self.findComportamentoByNome(nomeComp)
                if comportamento is not None:
                    # 3. Aggiunta di tutti gli stati del comportamento corrente
                    for stato in comp.findall('stati/stato'):
                        newStato = Stato(stato.attrib()['nome'])
                        comportamento.addStato(newStato)

                    # 4. Aggiunta dello stato iniziale al comportamento dato (con controllo degli errori)
                    nomeStatoIniziale = comp.attrib()['statoIniziale']
                    statoIniziale = comportamento.findStatoByNome(nomeStatoIniziale)
                    if statoIniziale is not None:
                        comportamento.statoIniziale = statoIniziale
                    else:
                        raise KeyError(f'Lo stato iniziale {nomeStatoIniziale} del comportamento {nomeComp} non è stato definito nella rete')

                    # 5. Aggiunta delle transizioni al comportamento dato (con controllo degli errori)
                    for trans in comp.findall('transizioni/transizione'):
                        nomeTrans = trans.attrib()['nome']
                        nomeStato0 = trans.attrib()['stato0']
                        nomeStato1 = trans.attrib()['stato1']
                        etichettaOsservabilita = trans.attrib()['osservabilita']
                        etichettaRilevanza = trans.attrib()['rilevanza']

                        # Verifichiamo che gli stati siano presenti nel comportamento
                        stato0 = comportamento.findStatoByNome(nomeStato0)
                        stato1 = comportamento.findStatoByNome(nomeStato1)
                        if stato0 is not None:
                            if stato1 is not None:
                                # 6. Aggiunta dell'eventoNecessario
                                # Verifichiamo se c'è un evento necessario per questa transizione
                                en = trans.find('eventoNecessario')
                                eventoNecessario = None
                                if en is not None:
                                    nomeEventoNecessario = en.attrib()['nome']
                                    nomeLinkEventoNecessario = en.attrib()['link']

                                    # Cerchiamo il link nel comportamento
                                    linkEventoNecessario = self.findLinkByNome(nomeLinkEventoNecessario)
                                    if linkEventoNecessario is not None:
                                        # Costruiamo l'evento necessario alla transizione
                                        eventoNecessario = Buffer(linkEventoNecessario, nomeEventoNecessario)
                                    else:
                                        raise KeyError(
                                            f'Il link {nomeLinkEventoNecessario} relativo all\'evento necessario {nomeEventoNecessario} della transizione {nomeTrans} del comportamento {nomeComp} non è stato definito nella rete')

                                # 7. Aggiunta degli eventi in output alla transizione
                                eventiOutput = []
                                for eo in trans.findall('eventiOutput/evento'):
                                    nomeEventoOutput = eo.attrib()['nome']
                                    nomeLinkEventoOutput = eo.attrib()['link']

                                    # Cerchiamo il link nel comportamento
                                    linkEventoOutput = self.findLinkByNome(nomeLinkEventoOutput)
                                    if linkEventoOutput is not None:
                                        # Costruiamo l'evento output e aggiungiamolo alla lista
                                        eventoOutput = Buffer(linkEventoOutput, nomeEventoOutput)
                                        eventiOutput.append(eventoOutput)
                                    else:
                                        raise KeyError(
                                            f'Il link {nomeLinkEventoOutput} relativo all\'evento output {nomeEventoOutput} della transizione {nomeTrans} del comportamento {nomeComp} non è stato definito nella rete')

                                # Se entrambi gli stati della transizione sono presenti, aggiungiamo la nuova transizione
                                newTransizione = Transizione(
                                    nomeTrans,
                                    stato0,
                                    stato1,
                                    eventoNecessario,
                                    eventiOutput,
                                    osservabilita=etichettaOsservabilita,
                                    rilevanza=etichettaRilevanza)

                            else:
                                raise KeyError(
                                    f'Lo stato {nomeStato1} della transizione {nomeTrans} non è stato definito nella rete')
                        else:
                            raise KeyError(
                                f'Lo stato {nomeStato0} della transizione {nomeTrans} non è stato definito nella rete')
                else:
                    raise KeyError(f'Il comportamento {nomeComp} non è stato definito nella rete')

            # 8. Compilazione delle transizioni uscenti in ciascuno stato
            # todo

            print("ciao")

        return out

    def addComportamento(self, comportamento: Comportamento):
        """
        Aggiunge un comportamento alla rete
        :param comportamento: il nuovo comportamento da aggiungere
        :return: None
        """
        self.comportamenti.append(comportamento)

    def findComportamentoByNome(self, nomeComportamento: str) -> Comportamento:
        """
        Cerca un comportamento nella rete a partire dal suo nome
        :param nomeComportamento: il nome del comportamento
        :return: se presente, il Comportamento, None altrimenti
        """
        for comportamento in self.comportamenti:
            if comportamento.nome == nomeComportamento:
                return comportamento
        return None

    def addLink(self, nome: str, nomeComp0: str, nomeComp1: str):
        """
        Aggiunge un link alla ReteFA dopo aver effettuato il controllo sull'esistenza dei comportamenti coi nomi dati
        :param nome: nome del link
        :param nomeComp0: nome del comportamento 0 del link
        :param nomeComp1: nome del comportamento 1 del link
        :return: None
        :raises:
            KeyError: se non esiste uno dei comportamenti che determinano gli estremi del link
        """
        # Recuperiamo/cerchiamo i comportamenti a partire dal nome
        comp0 = self.findComportamentoByNome(nomeComp0)
        comp1 = self.findComportamentoByNome(nomeComp1)

        # Se ci sono entrambi i comportamenti, aggiungiamo il link alla rete
        # Altrimenti lanciamo eccezioni specifiche
        if comp0 is not None:
            if comp1 is not None:
                self.links.append(Link(nome, comp0, comp1))
            else:
                raise KeyError(f'Il comportamento {nomeComp0} del link {nome} non è stato definito nella rete')
        else:
            raise KeyError(f'Il comportamento {nomeComp1} del link {nome} non è stato definito nella rete')

    def findLinkByNome(self, nome: str) -> Link:
        """
        Cerca un link nella rete a partire dal suo nome
        :param nome: il nome del link
        :return: se presente, il Link, None altrimenti
        """
        for link in self.links:
            if link.nome == nome:
                return link
        return None



## METODI ##


## MAIN ##

if __name__ == '__test1__':
    xsdPath = 'D:\\STORAGE\\Dropbox\\Dropbox\\000 Specialistica\\ASD\\Progetto ASD 2020\\input.xsd'
    xmlPath = 'D:\\STORAGE\\Dropbox\\Dropbox\\000 Specialistica\\ASD\\Progetto ASD 2020\\input.xml'

    out = ReteFA.validateXML(xmlPath)
    print(out)

if __name__ == '__main__':
    """Test per l'inizializzazione di una rete a partire da un input"""
    xmlPath = 'D:\\STORAGE\\Dropbox\\Dropbox\\000 Specialistica\\ASD\\Progetto ASD 2020\\input.xml'

    # import xml.etree.ElementTree as ET
    # tree = ET.parse(xmlPath)
    # root = tree.getroot()

    rete = ReteFA.fromXML(xmlPath)
    print(rete)
