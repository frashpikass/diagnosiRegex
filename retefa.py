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

    def clone(self):
        """
        Crea e ritorna una deep copy del buffer corrente
        :return: una deep copy del buffer corrente
        """
        return Buffer(self.link, str(self.evento))

    def __eq__(self, other):
        return self.link == other.link and self.evento == other.evento



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

    def __init__(self, nome: str):
        self.nome = nome
        self.transizioniUscenti = []

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

    def __init__(self, nome: str, statoIniziale: Stato = None):
        self.nome = nome
        self.stati = []
        self.transizioni = []
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

    def addTransizione(self, newTransizione: Transizione):
        """
        Aggiunge la transizione data alle transizioni di questo Comportamento
        :param newTransizione: la nuova Transizione da aggiungere
        :return: None
        """
        self.transizioni.append(newTransizione)


class Link(object):
    """
    Classe che descrive un link fra due comportamenti nella topologia della rete FA.
    """

    def __init__(self, nome: str, comportamento0: Comportamento, comportamento1: Comportamento):
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

    def __init__(self, nome: str):
        self.id = nome
        self.comportamenti = []
        self.links = []

    @staticmethod
    def validateXML(xml) -> bool:
        """
        Metodo per validare l'XML in input
        :return: true se l'XML è valido
        """
        xsdPath = 'inputs/input.xsd'
        schema = xmlschema.XMLSchema(xsdPath)
        return schema.is_valid(xml)

    @staticmethod
    def fromXML(xmlPath):
        """
        Costruisce la rete FA a partire dai dati contenuti nell'XML che la descrive
        :param xmlPath: xml che descrive la rete FA
        :return: la reteFA costruita a partire dall'XML
        """

        out = None

        """
        Costruzione della struttura dati in ordine tale da verificare che i riferimenti incrociati fra elementi della 
        struttura esistano.
        Costruiamo gli oggetti nel seguente ordine. Segno con * dove fare il controllo degli errori:
            1- comportamenti, comportamento(nome)
            2- links(nome, comp0*, comp1*) *controlla che esistano i comportamenti
            3- comportamenti, comportamento, stati, stato(nome)
            4- statoIniziale* del comportamento *controlla che esista lo stato indicato
            5- transizioni, transizione(nome, stato0*, stato1*, osservabilita, rilevanza) 
                *controlla che gli stati esistano
            6- eventualmente evento necessario della transizione eventoNecessario(nome, link*)
                *controlla che il link esista
            7- eventualmente eventiOutput(evento, link*) *controlla che il link esista
            
            8- compilazione delle transizioni uscenti
        """

        import xml.etree as ET

        # Validazione dell'XML
        if ReteFA.validateXML(xmlPath):
            tree = ET.ElementTree.parse(source=xmlPath)
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
                nome = link.attrib['nome']
                comp0 = link.attrib['comp0']
                comp1 = link.attrib['comp1']
                # Aggiungiamo il link descritto dagli attributi
                out.addLink(nome, comp0, comp1)

            # 3-4-5-6-7. Introduzione degli stati, dello stato iniziale e delle
            # transizioni (con etichette) nei comportamenti
            for comp in root.findall('comportamenti/comportamento'):
                nomeComp = comp.attrib['nome']
                # Cerco il comportamento nomeComp nella rete
                comportamento = out.findComportamentoByNome(nomeComp)
                if comportamento is not None:
                    # 3. Aggiunta di tutti gli stati del comportamento corrente
                    for stato in comp.findall('stati/stato'):
                        newStato = Stato(stato.attrib['nome'])
                        comportamento.addStato(newStato)

                    # 4. Aggiunta dello stato iniziale al comportamento dato (con controllo degli errori)
                    nomeStatoIniziale = comp.attrib['statoIniziale']
                    statoIniziale = comportamento.findStatoByNome(nomeStatoIniziale)
                    if statoIniziale is not None:
                        comportamento.statoIniziale = statoIniziale
                    else:
                        raise KeyError(f'Lo stato iniziale {nomeStatoIniziale} del comportamento {nomeComp} non è stato definito nella rete')

                    # 5. Aggiunta delle transizioni al comportamento dato (con controllo degli errori)
                    for trans in comp.findall('transizioni/transizione'):
                        nomeTrans = trans.attrib['nome']
                        nomeStato0 = trans.attrib['stato0']
                        nomeStato1 = trans.attrib['stato1']
                        etichettaOsservabilita = trans.attrib['osservabilita']
                        etichettaRilevanza = trans.attrib['rilevanza']

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
                                    nomeEventoNecessario = en.attrib['nome']
                                    nomeLinkEventoNecessario = en.attrib['link']

                                    # Cerchiamo il link nel comportamento
                                    linkEventoNecessario = out.findLinkByNome(nomeLinkEventoNecessario)
                                    if linkEventoNecessario is not None:
                                        # Costruiamo l'evento necessario alla transizione
                                        eventoNecessario = Buffer(linkEventoNecessario, nomeEventoNecessario)
                                    else:
                                        raise KeyError(
                                            f'Il link {nomeLinkEventoNecessario} relativo all\'evento necessario {nomeEventoNecessario} della transizione {nomeTrans} del comportamento {nomeComp} non è stato definito nella rete')

                                # 7. Aggiunta degli eventi in output alla transizione
                                eventiOutput = []
                                for eo in trans.findall('eventiOutput/evento'):
                                    nomeEventoOutput = eo.attrib['nome']
                                    nomeLinkEventoOutput = eo.attrib['link']

                                    # Cerchiamo il link nel comportamento
                                    linkEventoOutput = out.findLinkByNome(nomeLinkEventoOutput)
                                    if linkEventoOutput is not None:
                                        # Costruiamo l'evento output e aggiungiamolo alla lista
                                        eventoOutput = Buffer(linkEventoOutput, nomeEventoOutput)
                                        eventiOutput.append(eventoOutput)
                                    else:
                                        raise KeyError(
                                            f'Il link {nomeLinkEventoOutput} relativo all\'evento output {nomeEventoOutput} della transizione {nomeTrans} del comportamento {nomeComp} non è stato definito nella rete')

                                # Se entrambi gli stati della transizione sono presenti,
                                # aggiungiamo la nuova transizione
                                newTransizione = Transizione(
                                    nomeTrans,
                                    stato0,
                                    stato1,
                                    eventoNecessario,
                                    eventiOutput,
                                    osservabilita=etichettaOsservabilita,
                                    rilevanza=etichettaRilevanza)
                                comportamento.addTransizione(newTransizione)


                            else:
                                raise KeyError(
                                    f'Lo stato {nomeStato1} della transizione {nomeTrans} non è stato definito nella rete')
                        else:
                            raise KeyError(
                                f'Lo stato {nomeStato0} della transizione {nomeTrans} non è stato definito nella rete')
                else:
                    raise KeyError(f'Il comportamento {nomeComp} non è stato definito nella rete')

            # 8. Compilazione delle transizioni uscenti in ciascuno stato
            # Scorriamo i comportamenti della ReteFA
            for comport in out.comportamenti:
                # Scorriamo le transizioni del comportamento
                transiz: Transizione
                for transiz in comport.transizioni:
                    # Aggiungiamo la transizione corrente alle transizioni uscenti
                    # dello stato0 della transizione corrente
                    transiz.stato0.addTransizioneUscente(transiz)

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
                raise KeyError(f'Il comportamento {nomeComp1} del link {nome} non è stato definito nella rete')
        else:
            raise KeyError(f'Il comportamento {nomeComp0} del link {nome} non è stato definito nella rete')

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


class Nodo:
    def __init__(self):
        self.nome = None
        self.stati = []
        self.contenutoLink = []
        self.isPotato = True
        self.isFinale = False

    def addStato(self, stato: Stato) -> None:
        """
        Aggiunge uno Stato della ReteFA al nodo corrente
        :param stato: lo Stato da aggiungere
        """
        self.stati.append(stato)

    def addContenutoLink(self, buffer: Buffer) -> None:
        """
        Aggiunge un oggetto Buffer della ReteFA al contenuto del link del nodo corrente
        :param buffer: il buffer da aggiungere al contenuto del link
        """
        self.contenutoLink.append(buffer)

    def clone(self):
        """
        Crea e ritorna una deep copy del nodo corrente
        :return: una deep copy del nodo corrente
        """
        out = Nodo()

        out.nome = str(self.nome)

        stato: Stato
        for stato in self.stati:
            out.addStato(stato)

        buffer: Buffer
        for buffer in self.contenutoLink:
            out.addContenutoLink(buffer.clone())

        out.isPotato = self.isPotato
        out.isFinale = self.isFinale

        return out

    def __eq__(self, other):
        # Verifico se ogni stato in questo nodo è anche nell'altro nodo
        # todo: verificare se funziona
        # todo: forse ci converrebbe definire gli stati come fossero un set? Quanto ci costa il cast a set?
        # todo: verifica se per fare il confronto fra contenutoLink, l'operatore == chiama __eq__ per ogni confronto fra elementi
        other: Nodo
        return self.isFinale == other.isFinale \
            and set(self.stati) == set(other.stati) \
            and set(self.contenutoLink) == set(other.contenutoLink)



    def verificaFattibilitaTransizione(self, transizione: Transizione):
        """
        Ritorna il nodo successivo dello SC a partire dal nodo corrente se la transizione data può scattare,
        None altrimenti.
        Il nodo restituito è già flaggato come finale se tutti i suoi link sono scarichi (cioè contengono evento nullo)
        :param transizione: la transizione da verificare sul nodo corrente
        :return: il nodo successivo dello Spazio Comportamentale se la transizione è fattibile. None altrimenti
        """

        # Partiamo dalla transizione in input e cerchiamo di capire se può scattare.
        # Leggiamo l'evento necessario allo scatto della transizione (che è un buffer, a livello di struttura dati)
        # Nel nodo in uscita cerchiamo il contenuto del buffer relativo al link specifico (estraiamo il contenuto dei
        # buffer del link del nodo).
        # Cerca nel contenuto dei link del nodo l'evento necessario alla transizione.
        # Se entrambe le verifiche sugli eventi necessari e in out sono positive, calcoliamo il nodo successivo ponendo:
        # - come stato relativo al comportamento coinvolto nella transizione, lo stato1 della transizione
        # - gli stati relativi agli altri comportamenti sul nodo, inalterati
        # - il contenuto dei buffer dei link coinvolti nella transizione, aggiornato con gli eventi uscenti
        # - il flag isFinale a true se il nodo è finale

        # 1. Verifica evento necessario
        # Se l'evento necessario è nel buffer del link corretto procediamo
        bufferEventoNec: Buffer
        bufferEventoNec = self.cercaContenutoLink(transizione.eventoNecessario.link)
        if bufferEventoNec is not None and bufferEventoNec.evento == transizione.eventoNecessario.evento:
            # Inizializziamo il nodo in output a questa funzione
            # creando un clone del nodo in input, che poi modificheremo in corso d'opera
            # in modo da rispecchiare gli effetti della transizione
            nodoOutput: Nodo
            nodoOutput = self.clone()  # Nota: l'operazione di clonazione avviene qui per risparmiare cicli

            # Sostituiamo nel buffer del nodo in uscita, relativamente al contenuto del link dell'evento necessario
            # alla transizione, un evento nullo (quindi è come se consumassimo l'evento necessario)
            nodoOutput.cercaContenutoLink(transizione.eventoNecessario.link).evento = ""

            # 2. Verifica che i link che saranno riempiti dalla transizione siano scarichi
            # Recuperiamo gli eventi in uscita alla transizione, poi ne verifichiamo la fattibilità
            # ovvero verifichiamo che i buffer dei link coinvolti negli eventi in uscita siano liberi
            eo: Buffer
            for eo in transizione.eventiOutput:
                # L'evento vuoto ha il link dell'evento in uscita alla transizione e il buffer evento del link vuoto
                # Cerchiamo il buffer relativo al link da riempire secondo la transizione
                bufferOutput = nodoOutput.cercaContenutoLink(eo.link)

                # Se il buffer è già pieno
                if bufferOutput.evento != "":
                    # allora la transizione non è fattibile e ritorniamo None come nodo output
                    return None
                else:
                    # altrimenti dobbiamo inserire l'evento in uscita nei buffer
                    # del link del nodo in uscita (quindi lo aggiorniamo)
                    bufferOutput.evento = eo.evento

            # Infine aggiorniamo nel nodoOutput lo stato relativo alla transizione corrente
            # con lo stato successivo della transizione
            nodoOutput.stati[nodoOutput.stati.index(transizione.stato0)] = transizione.stato1

            # Verifichiamo che tutti i suoi link siano scarichi per decidere se
            # flaggare il nodoOutput come finale o meno
            nodoOutput.isFinale = True
            buf: Buffer
            for buf in nodoOutput.contenutoLink:
                if buf.evento != "":
                    nodoOutput.isFinale = False
                    break

            # Dopo averlo costruito e popolato, ritorniamo il nodo output generato dalla transizione
            return nodoOutput

        else:
            # Se la transizione non è fattibile, ritorniamo None come nodo output
            return None

    def cercaContenutoLink(self, link: Link) -> Buffer:
        """
        Legge in questo nodo il buffer relativo al link dato e lo ritorna.
        :param link: il link da leggere
        :return: il buffer del link passato in input
        """
        buffer: Buffer
        for buffer in self.contenutoLink:
            if buffer.link == link:
                return buffer
        return None


class Arco:
    def __init__(self, nodo0: Nodo, nodo1: Nodo, transizione: Transizione):
        self.nodo0 = nodo0
        self.nodo1 = nodo1
        self.transizione = transizione
        self.isPotato = True


class SpazioComportamentale:
    def __init__(self, rete: ReteFA):
        """
        Inizializza lo Spazio Comportamentale a partire da una ReteFA
        :param rete: la ReteFA in input
        """
        # Inizializza gli attributi
        self.nodi = []
        self.archi = []
        self.nodoIniziale = Nodo()

        # Generazione del nodo iniziale dell'SC
        # Insieriamo tutti gli stati iniziali di tutti i comportamenti
        comp: Comportamento
        for comp in rete.comportamenti:
            self.nodoIniziale.addStato(comp.statoIniziale)

        # Inserisce un buffer vuoto per ciascun link presente nella rete
        link: Link
        for link in rete.links:
            self.nodoIniziale.addContenutoLink(Buffer(link, ""))

        # Avendo tutti i buffer vuoti, il nodo iniziale è sempre anche finale
        self.nodoIniziale.isFinale = True

        # Ora il nodo iniziale è inizializzato
        # Aggiungiamo il nodo iniziale allo SC
        self.nodi.append(self.nodoIniziale)

        # Ora dobbiamo esplorare la Rete FA per costruire lo SC

        # Inizializzo una pila di nodi da esplorare
        nodiDaEsplorare = []

        # Inizializza il nodo di SC correntemente osservato
        nodoCorr = self.nodoIniziale

        # Esploriamo la rete FA e creiamo lo spazio comportamentale
        # a partire dal nodo iniziale
        while nodoCorr is not None:
            # Scorri la lista degli stati correnti
            # del nodo corrente
            for stato in nodoCorr.stati:
                for trans in stato.transizioniUscenti:
                    # Ricaviamo il nodo successivo a partire dal nodo corrente
                    # verificando la fattibilità della transizione uscente
                    nodoSucc = nodoCorr.verificaFattibilitaTransizione(trans)

                    # Se esiste una transizione fattibile (ovvero il nodo successivo non è None)
                    if nodoSucc is not None:
                        rif = self.ricercaNodo(nodoSucc)

                        # Se il nodo non è già nell'SC
                        if rif is None:
                            # Aggiungo il nodo all'SC
                            self.addNodo(nodoSucc)
                            # Push del nodo sullo stack di nodi da esplorare
                            nodiDaEsplorare.append(nodoSucc) # append è come push sulle liste
                            # ATTENZIONE: usare la lista di Python come stack può
                            # essere inefficiente https://www.geeksforgeeks.org/stack-in-python/

                        # Aggiungo sempre l'arco legato alla transizione fattibile
                        self.addArco(Arco(nodoCorr, nodoSucc, trans))

            # Recuperiamo il nuovo nodo corrente da studiare
            nodoCorr = nodiDaEsplorare.pop()
            # Proseguiamo col while

    def addArco(self, arco: Arco) -> None:
        """
        Aggiunge un arco alla lista degli archi di questo Spazio Comportamentale
        :param arco: l'arco da aggiungere
        """
        self.archi.append(arco)

    def addNodo(self, nodo: Nodo) -> None:
        """
        Aggiunge un nodo alla lista degli nodi di questo Spazio Comportamentale
        :param nodo: il nodo da aggiungere
        """
        self.nodi.append(nodo)

    def ricercaNodo(self, nodo: Nodo) -> Nodo:
        """
        Ricerca per valore il nodo dato fra i nodi dello SpazioComportamentale
        :param nodo:
        :return:
        """
        # Scorriamo i nodi dello spazio comportamentale
        # alla ricerca di un nodo che sia come quello in input
        for nodoCorr in self.nodi:
            # # Verifichiamo tutte le features del nodo
            # # da trovare confrontandole con quelle del nodo
            # # correntemente analizzato dal ciclo partendo da
            # # quelle meno dispendiose per risparmiare cicli
            #
            # # Se il nodo corrente non è come il nodo in input
            # # rispetto a isFinale, passa all'iter successiva
            # if nodo.isFinale != nodoCorr.isFinale:
            #     continue
            #
            # # (ipotizziamo ora che vi siano sempre meno stati che li
            # # quindi valutiamo prima la corrispondenza sugli stati)
            # # Se il nodo corrente non è come il nodo in input
            # # rispetto agli stati (confronto per valore con cortocircuito),
            # # passa all'iterazione successiva del for each
            # # todo: forse è meglio gestire gli stati come set?
            # if set(nodo.stati) != set(nodoCorr.stati):
            #     continue
            #
            # # Se il nodo corrente non è come il nodo in input
            # # rispetto al contenuto dei buffer
            # # (confronto per valore con cortocircuito),
            # # passa all'iterazione successiva
            # # todo: controlla che faccia bene il confronto fra i buffer!
            # if set(nodo.contenutoLink) != set(nodoCorr.contenutoLink):
            #     continue

            # Se abbiamo trovato il nodo corrispondente a quello in input
            # lo ritorniamo
            if nodo == nodoCorr:
                return nodoCorr

        # Se il nodo non è stato trovato
        return None


## METODI ##


## MAIN ##

if __name__ == '__test1__':
    xmlPath = 'inputs/input.xml'

    out = ReteFA.validateXML(xmlPath)
    print(out)

if __name__ == '__main__':
    """Test per l'inizializzazione di una rete a partire da un input"""
    xmlPath = 'inputs/input.xml'

    # import xml.etree.ElementTree as ET
    # tree = ET.parse(xmlPath)
    # root = tree.getroot()
    rete = ReteFA.fromXML(xmlPath)
    print(rete)
