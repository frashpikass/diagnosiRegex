"""
File di descrizione degli elementi della struttura dati in input.
"""
from functools import singledispatchmethod
from typing import List, Dict
import xmlschema
import copy
import xml.etree.ElementTree as ET
import argparse
from pickle import dumps, loads, dump, load
from base64 import b64encode, b64decode
from datetime import datetime
import subprocess
import time
import os

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

    def __str__(self):
        return (self.evento if self.evento != "" else "ε") + "(" + self.link.nome + ")"

    def __eq__(self, other):
        return self.link == other.link and self.evento == other.evento

    def __hash__(self):
        return hash((self.link, self.evento))


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

    def strEventiInputOutput(self):
        """
        Genera per la transizione corrente la stringa che descrive gli eventi in ingresso e uscita
        :return: stringa di eventi in input e output
        """
        eventi_out = "" + " ".join([str(e) for e in self.eventiOutput])
        if eventi_out != "":
            eventi_out = f"/{{{eventi_out}}}"
        out = f"{str(self.eventoNecessario) if self.eventoNecessario else ''}{eventi_out}"
        return out

    def __str__(self):
        return self.nome + ": " + self.stato0.nome + "->" + self.stato1.nome + ", " + self.strEventiInputOutput()


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

        # Validazione dell'XML
        if ReteFA.validateXML(xmlPath):
            tree = ET.parse(source=xmlPath)
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
                        messaggio = f'Lo stato iniziale {nomeStatoIniziale} del comportamento {nomeComp} non è stato definito nella rete'
                        Log.new("fromXML, KeyError", messaggio)
                        raise KeyError(messaggio)

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
                                        messaggio = f'Il link {nomeLinkEventoNecessario} relativo all\'evento ' \
                                                    f'necessario {nomeEventoNecessario} della transizione {nomeTrans}' \
                                                    f' del comportamento {nomeComp} non è stato definito nella rete'
                                        Log.new("fromXML, KeyError", messaggio)
                                        raise KeyError(messaggio)

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
                                        messaggio = f'Il link {nomeLinkEventoOutput} relativo all\'evento output ' \
                                                    f'{nomeEventoOutput} della transizione {nomeTrans} del ' \
                                                    f'comportamento {nomeComp} non è stato definito nella rete'
                                        Log.new("fromXML, KeyError", messaggio)
                                        raise KeyError()

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
                                messaggio = f'Lo stato {nomeStato1} della transizione {nomeTrans} non è stato ' \
                                            f'definito nella rete'
                                Log.new("fromXML, KeyError", messaggio)
                                raise KeyError(messaggio)
                        else:
                            messaggio = f'Lo stato {nomeStato0} della transizione {nomeTrans} non è stato ' \
                                        f'definito nella rete'
                            Log.new("fromXML, KeyError", messaggio)
                            raise KeyError(messaggio)
                else:
                    messaggio = f'Il comportamento {nomeComp} non è stato definito nella rete'
                    Log.new("fromXML, KeyError", messaggio)
                    raise KeyError(messaggio)

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
                messaggio = f'Il comportamento {nomeComp1} del link {nome} non è stato definito nella rete'
                Log.new("addLink, KeyError", messaggio)
                raise KeyError(messaggio)
        else:
            messaggio = f'Il comportamento {nomeComp0} del link {nome} non è stato definito nella rete'
            Log.new("addLink, KeyError", messaggio)
            raise KeyError(messaggio)

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

    def verificaOsservazioneLineare(self, osservazioneLineare: List[str]) -> bool:
        """
        Verifica che tutte le etichette di Osservabilità presenti nell'osservazione lineare esistano associate alle
        transizioni di questa ReteFA.
        :param osservazioneLineare: una lista di etichette di osservabilità
        :return: True se l'osservazione lineare è compatibile con questa ReteFA
        :raises ValueError: se l'osservazione lineare è incompatibile con questa ReteFA
        """

        # Prendiamo tutte le etichette di osservazioneLineare, una volta sola
        setEtichette = set(osservazioneLineare)

        # Per ciascuna etichetta nell'insieme, verifico che
        # esista nella reteFA una transizione con tale etichetta associata
        for etichetta in setEtichette:
            trovata = False

            c: Comportamento
            for c in self.comportamenti:
                t: Transizione
                for t in c.transizioni:
                    if t.osservabilita == etichetta:
                        trovata = True
                        break
                if trovata:
                    break
            if not trovata:
                messaggio = f"L'etichetta di osservabilità '{etichetta}' non è presente in nessuna transizione "\
                            f"della ReteFA inserita."
                Log.new("verificaOsservazioneLineare, ValueError", messaggio)
                raise ValueError(messaggio)
        return True

    def makeDotGraph(self) -> str:
        """
        Genera la rappresentazione in formato DOT della ReteFA, visualizzabile tramite GraphViz.
        :return: la rappresentazione in formato DOT della ReteFA
        """
        comportamenti = ""
        stati = ""
        transizioni = ""
        links = ""
        eventi = ""

        comp = []
        c: Comportamento
        for c in self.comportamenti:
            label = "\n\t\t".join([f"<b>{c.nome}</b>"]
                                  + [f"<br/>{t.nome}: {t.strEventiInputOutput()}" for t in c.transizioni])

            stati = "\n\t\t".join([f"c{c.nome}_start [style=invis]"]
                                  + [f"c{c.nome}_{s.nome} [label=<<b>{s.nome}</b>>]" for s in c.stati])

            trans = [f"c{c.nome}_start -> c{c.nome}_{c.statoIniziale.nome}"]
            s: Stato
            for s in c.stati:
                for t in s.transizioniUscenti:
                    osservabilita = f"<br/><font color=\"green4\">{t.osservabilita}</font>" if t.osservabilita != "" else ""
                    rilevanza = f"<br/><font color=\"red\">{t.rilevanza}</font>" if t.rilevanza != "" else ""
                    trans.append(f"c{c.nome}_{t.stato0.nome} -> c{c.nome}_{t.stato1.nome} [label=<{t.nome}{osservabilita}{rilevanza}>]")
            transizioni = "\n\t\t".join(trans)

            comportamento = f"""subgraph cluster_{c.nome} {{
        node [shape=ellipse]
        label = <{label}>
        
        // Transizioni
        {transizioni}

        // Stati
        {stati}
    }}"""
            comp.append(comportamento)
        # Fine for sui comportamenti
        comportamenti = "\n\n\t".join(comp)

        links = "\n\t".join([f"c{li.comportamento0.nome}_start -> c{li.comportamento1.nome}_start [label=\"{li.nome}\" ltail=cluster_{li.comportamento0.nome} lhead=cluster_{li.comportamento1.nome}]" for li in self.links])

        # Compilo l'output
        out = f"""digraph ReteFA {{
    graph [compound=true]
    node [shape=record]
    // LINKS
    {links}

    // COMPORTAMENTI
    {comportamenti}
}}
"""
        return out

    def logStats(self):
        """
        Genera delle statistiche su questa ReteFA e le salva nel Log
        """
        Log.new("Statistiche sulla Rete FA", "")
        Log.new("\tNumero comportamenti", f"{len(self.comportamenti)}")
        Log.new("\tNumero stati", f"{sum([len(c.stati) for c in self.comportamenti])}")
        Log.new("\tNumero transizioni", f"{sum([len(c.stati) for c in self.comportamenti])}")


class Nodo:
    """
    Classe che descrive un nodo in uno SpazioComportamentale
    """
    def __init__(self):
        self.nome = None
        self.stati = []
        self.contenutoLink = []
        self.isPotato = True
        self.isFinale = False
        self.indiceOsservazione = 0
        self.archiUscenti = []
        self.chiusura = None

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
        Crea e ritorna una deep copy del nodo corrente.
        Warning: le liste di adiacenza non saranno copiate!
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
        # todo: forse ci converrebbe definire gli stati come fossero un set? Quanto ci costa il cast a set?
        # todo: rivedere questo eq - il confronto di uguaglianza così va bene solo fino a Compito 3. == non farà mai più il confronto per riferimento!
        other: Nodo
        if other:
            return self.indiceOsservazione == other.indiceOsservazione \
                   and self.isFinale == other.isFinale \
                   and set(self.stati) == set(other.stati) \
                   and set(self.contenutoLink) == set(other.contenutoLink)
        else:
            return False

    def __str__(self):
        out = f"Nome: {self.nome}, Stati:"

        for stato in self.stati:
            out = out + " " + stato.nome
        out = out + ", Buffer:"

        for buffer in self.contenutoLink:
            out = out + " " + str(buffer)

        if self.isFinale:
            out = out + ", finale"

        out = out + ", Indice Osservazione " + str(self.indiceOsservazione)

        return out

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

        # Inizializziamo il nodo in output a questa funzione
        # creando un clone del nodo in input, che poi modificheremo in corso d'opera
        # in modo da rispecchiare gli effetti della transizione
        nodoOutput: Nodo
        nodoOutput = self.clone()

        # 1. Verifica se è presente l'evento necessario
        if transizione.eventoNecessario is not None:
            bufferEventoNec: Buffer
            bufferEventoNec = nodoOutput.cercaContenutoLink(transizione.eventoNecessario.link)
            # Se l'evento necessario è nel buffer del link corretto, lo consumiamo e procediamo
            if bufferEventoNec.evento == transizione.eventoNecessario.evento:
                # consumiamo l'evento necessario
                bufferEventoNec.evento = ""
                # procediamo
            else:
                # La transizione non è fattibile perché manca l'evento necessario
                # ritorniamo None come nodo output
                return None

        # 2. Verifichiamo se c'è spazio nel buffer del nodo per gli eventi in output

        # Verifica che i link che saranno riempiti dalla transizione siano scarichi
        # Recuperiamo gli eventi in uscita alla transizione, poi ne verifichiamo la fattibilità
        # ovvero verifichiamo che i buffer dei link coinvolti negli eventi in uscita siano liberi
        eo: Buffer
        for eo in transizione.eventiOutput:
            # L'evento vuoto ha il link dell'evento in uscita alla transizione e il buffer evento del link vuoto
            # Cerchiamo il buffer relativo al link da riempire secondo la transizione
            bufferOutput = nodoOutput.cercaContenutoLink(eo.link)

            # Se il buffer è già pieno
            if bufferOutput.evento != "":
                # allora la transizione non è fattibile: ritorniamo None come nodo output
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
    """
        Classe che descrive un arco in uno SpazioComportamentale
    """
    def __init__(self, nodo0: Nodo, nodo1: Nodo, transizione: Transizione, rilevanza: str, osservabilita: str):
        self.nodo0 = nodo0
        self.nodo1 = nodo1
        self.transizione = transizione
        self.isPotato = True
        self.rilevanza = rilevanza
        self.osservabilita = osservabilita

    def __str__(self):
        if self.transizione:
            return "(" + self.nodo0.nome + "," + self.nodo1.nome + "), " + self.transizione.nome + ", " + \
                   self.transizione.osservabilita + ", " + self.rilevanza
        else:
            return "(" + self.nodo0.nome + "," + self.nodo1.nome + "), " + self.rilevanza


class SpazioComportamentale:
    """
    Classe che descrive uno Spazio Comportamentale
    """
    ## VARIABILI DEBUG ##
    debug_counter = 1

    def __init__(self):
        self.nodi: List[Nodo]
        self.archi: List[Arco]
        self.nodoIniziale: Nodo

        self.nodi = []
        self.archi = []
        self.nodoIniziale = Nodo()

    def creaSpazioComportamentale(self, rete: ReteFA):
        """
        Crea lo Spazio Comportamentale a partire da una ReteFA
        :param rete: la ReteFA in input
        """

        # Inizializziamo il nodo iniziale
        self.creaNodoIniziale(rete)

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
            # Scorri la lista degli stati correnti del nodo corrente
            # scorri ogni transizione uscente di ciascuno stato corrente
            for stato in nodoCorr.stati:
                for trans in stato.transizioniUscenti:
                    # Ricaviamo il nodo successivo a partire dal nodo corrente
                    # verificando la fattibilità della transizione uscente
                    nodoSucc = nodoCorr.verificaFattibilitaTransizione(trans)

                    # Se esiste una transizione fattibile (ovvero il nodo successivo non è None)
                    if nodoSucc is not None:
                        # Cerco nell'SC il riferimento al nodo in uscita alla transizione
                        rif = self.ricercaNodo(nodoSucc)

                        # Se il nodo non è già nell'SC, dunque non è stato trovato
                        if rif is None:
                            # Aggiungo il nodo all'SC
                            self.addNodo(nodoSucc)
                            # Push del nodo sullo stack di nodi da esplorare
                            nodiDaEsplorare.append(nodoSucc)  # append è come push sulle liste
                            # ATTENZIONE: usare la lista di Python come stack può
                            # essere inefficiente https://www.geeksforgeeks.org/stack-in-python/
                            rif = nodoSucc

                        # Aggiungo sempre l'arco legato alla transizione fattibile
                        self.addArco(Arco(nodoCorr, rif, trans, trans.rilevanza, trans.osservabilita))

            # Recuperiamo il nuovo nodo corrente da studiare, se ci sono nodi correnti
            if nodiDaEsplorare:
                nodoCorr = nodiDaEsplorare.pop()
            else:
                # Altrimenti, non c'è nessun nodo corrente
                nodoCorr = None
            # Proseguiamo col while

    def creaSpazioComportamentaleOsservazioneLineare(self, rete: ReteFA, osservazioneLineare: List[str]):
        """
        Crea lo Spazio Comportamentale relativo all'osservazione lineare a partire da una ReteFA in ingresso.
        L'osservazione lineare è un array di etichette di osservazioni sulle transizioni.
        :param rete: la ReteFA in input
        :param osservazioneLineare: l'osservazione lineare in input
        :raises ValueError: se l'osservazione lineare in input presenta errori
        """

        # Verifichiamo la validità dell'osservazione lineare in input
        rete.verificaOsservazioneLineare(osservazioneLineare)

        # Inizializziamo il nodo iniziale
        self.creaNodoIniziale(rete)

        # Inizializziamo a 0 l'indice dell'osservazione del nodoIniziale
        self.nodoIniziale.indiceOsservazione = 0
        self.nodoIniziale.isFinale = self.nodoIniziale.isFinale and (self.nodoIniziale.indiceOsservazione == len(
            osservazioneLineare))

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
            # Scorri la lista degli stati correnti del nodo corrente
            # scorri ogni transizione uscente di ciascuno stato corrente
            for stato in nodoCorr.stati:
                for trans in stato.transizioniUscenti:
                    # Ricaviamo il nodo successivo a partire dal nodo corrente

                    # (filtro) Procedi lungo questo ramo solo se
                    # - la transizione ha osservabilità nulla
                    # - oppure se ha un'etichetta di osservabilità che ci aspettiamo nell'osservazione lineare
                    if (trans.osservabilita == "") \
                            or (nodoCorr.indiceOsservazione < len(osservazioneLineare)
                                and trans.osservabilita == osservazioneLineare[nodoCorr.indiceOsservazione]):

                        # verificando la fattibilità della transizione uscente
                        nodoSucc = nodoCorr.verificaFattibilitaTransizione(trans)

                        # Se esiste una transizione fattibile (ovvero il nodo successivo non è None)
                        if nodoSucc is not None:

                            # Aggiungiamo info sull'indice di osservazione
                            if trans.osservabilita == "":
                                nodoSucc.indiceOsservazione = nodoCorr.indiceOsservazione
                            else:  # ovvero se la transizione è osservabile e corrisponde all'osservazione successiva
                                nodoSucc.indiceOsservazione = nodoCorr.indiceOsservazione + 1

                            # impostiamo correttamente il flag isFinale del nodo successivo
                            nodoSucc.isFinale = nodoSucc.isFinale and (
                                    nodoSucc.indiceOsservazione == len(osservazioneLineare))

                            # Cerco nell'SC il riferimento al nodo in uscita alla transizione
                            rif = self.ricercaNodo(nodoSucc)

                            # Se il nodo non è già nell'SC, dunque non è stato trovato
                            if rif is None:
                                # Aggiungo il nodo all'SC
                                self.addNodo(nodoSucc)
                                # Push del nodo sullo stack di nodi da esplorare
                                nodiDaEsplorare.append(nodoSucc)  # append è come push sulle liste
                                # ATTENZIONE: usare la lista di Python come stack può
                                # essere inefficiente https://www.geeksforgeeks.org/stack-in-python/
                                rif = nodoSucc

                            # Aggiungo sempre l'arco legato alla transizione fattibile
                            self.addArco(Arco(nodoCorr, rif, trans, trans.rilevanza, trans.osservabilita))

            if nodiDaEsplorare:
                nodoCorr = nodiDaEsplorare.pop()
            else:
                # Altrimenti, non c'è nessun nodo corrente
                nodoCorr = None
            # Proseguiamo col while

    def creaNodoIniziale(self, rete: ReteFA):
        """
        Generazione del nodo iniziale dello SC
        :param rete: la ReteFA in input
        """
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

    def addArco(self, arco: Arco) -> None:
        """
        Aggiunge un arco alla lista degli archi di questo Spazio Comportamentale
        e alla lista di archi uscenti dal nodo di origine dell'arco
        :param arco: l'arco da aggiungere
        """
        self.archi.append(arco)
        arco.nodo0.archiUscenti.append(arco)

    def addNodo(self, nodo: Nodo) -> None:
        """
        Aggiunge un nodo alla lista degli nodi di questo Spazio Comportamentale
        :param nodo: il nodo da aggiungere
        """
        self.nodi.append(nodo)

    def ricercaNodo(self, nodo: Nodo) -> Nodo:
        """
        Ricerca per valore il nodo dato fra i nodi dello SpazioComportamentale
        :param nodo: il nodo da cercare per valore in questa struttura
        :return: il riferimento al nodo cercato se presente, None altrimenti
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
            ## NOTA: questo codice serve per riparare l'== in caso in cui ci venga in mente che il confronto per valore
            ## non ci piace più

            # Se abbiamo trovato il nodo corrispondente a quello in input
            # lo ritorniamo
            if nodo == nodoCorr:
                return nodoCorr

        # Se il nodo non è stato trovato
        return None

    def decidiPotatura(self) -> None:
        """
        Decide dove potare lo Spazio Comportamentale segnando come isPotato nodi e archi che non portano a stati finali.
        """
        # precondizione: ogni nuovo nodo e arco ha inizialmente isPotato=true
        self.setAllIsPotato(True)

        # Per determinare quali nodi e quali archi vadano potati
        # parto da ciascun nodo finale dell'SC e risalgo gli archi in ingresso

        # Inizializzo la pila di archi da esplorare
        archiDaEsplorare = []

        # Ciclo che esplora i nodi finali
        for nodoFinale in self.nodi:
            # La condizione su isPotato ci risparmia di visitare nodi già esplorati
            # Questo meccanismo evita di bloccarsi sui cicli del grafo
            if nodoFinale.isFinale and nodoFinale.isPotato:
                # Inizializzo il nodo corrente al nodo finale rintracciato dal ciclo esterno
                nodoCorrente = nodoFinale

                # Ciclo che esplora i nodi e gli archi entranti a partire da nodoFinale.
                # Inizializzo nextArco a un valore non nullo
                nextArco: Arco
                nextArco = not None
                while nextArco is not None:
                    nodoCorrente.isPotato = False
                    for arco in self.archi:
                        if arco.nodo1 == nodoCorrente:
                            arco.isPotato = False
                            # Faccio il push dell'arco da eplorare solo se non ho ancora visitato il nodo
                            # Questo meccanismo evita i cicli sul grafo
                            if arco.nodo0.isPotato:
                                archiDaEsplorare.append(arco)
                    # Estrai il prossimo arco da esplorare se c'è
                    if archiDaEsplorare:
                        nextArco = archiDaEsplorare.pop()

                        # Estrai il prossimo nodo da esplorare dal prossimo arco (se esiste)
                        if nextArco is not None:
                            nodoCorrente = nextArco.nodo0
                    else:
                        # Se non c'è inizializziamo l'arco
                        nextArco = None

    def potaturaArchi(self) -> None:
        """
        Rimuovi dallo spazio comportamentale solo gli archi con IsPotato == True
        """
        # Pota gli archi da potare, sia dalla lista degli archi,
        # sia dalle liste d'adiacenza di ciascun nodo

        # Elimina gli archi da potare
        self.archi = [a for a in self.archi if not a.isPotato]

        # Elimino gli archi potati dalle liste di adiacenza di ogni nodo non potato
        for nodo in self.nodi:
            nodo.archiUscenti = [a for a in nodo.archiUscenti if not a.isPotato]

    def potatura(self) -> None:
        """
        Rimuovi dallo spazio comportamentale tutti i nodi e tutti gli archi con ssPotato == True.
        Saranno potati anche tutti gli archi entranti e uscenti in ciascun nodo potato.
        """
        # Copiamo i nodi dello spazio comportamentale non potati
        nodiClone = []
        # La copia avviene per riferimento e non per valore
        # Effettua potatura dei nodi da potare e indica come da potare gli archi ad essi connessi
        for nodo in self.nodi:
            if not nodo.isPotato:
                nodiClone.append(nodo)
            else:
                # flaggo come da potare tutti gli archi entranti e uscenti dal nodo
                a: Arco
                for a in self.archi:
                    if a.nodo0 is nodo or a.nodo1 is nodo:
                        a.isPotato = True
        # Aggiorno i nodi coi nodi non potati
        self.nodi = nodiClone
        # Pota gli archi da potare, sia dalla lista degli archi,
        # sia dalle liste d'adiacenza di ciascun nodo
        self.potaturaArchi()

    def potaturaRidenominazione(self) -> None:
        """
        Decide quali nodi e archi potare (ovvero quelli che non portano ad un nodo finale), li rimuove dallo Spazio
        Comportamentale e dunque li ridenomina usando un ID progressivo dato dall'ordine di esplorazione.

        :raises ValueError: se lo spazio comportamentale è vuoto prima o dopo la potatura
        """
        # Verifichiamo se ci sono nodi nello spazio comportamentale, in tal caso la potatura non ha senso
        if not self.nodi or not self.archi:
            messaggio = "Impossibile procedere con la potatura: lo spazio comportamentale è vuoto. " \
                        "Verificare gli input."
            Log.new("potaturaRidenominazione, ValueError", messaggio)
            raise ValueError(messaggio)

        # Decidi quali archi e quali nodi potare
        self.decidiPotatura()

        # Effettua potatura e ridenominazione dei nodi
        # Logga le stat prima della potatura
        nodi_pre_potatura = len(self.nodi)
        archi_pre_potatura = len(self.archi)

        # Elimina nodi e archi da potare
        self.potatura()

        # Logga le stat dopo la potatura
        nodi_post_potatura = len(self.nodi)
        archi_post_potatura = len(self.archi)
        Log.new("Potatura e ridenominazione","")
        Log.new("\tStati potati", f"{nodi_post_potatura-nodi_pre_potatura}")
        Log.new("\tTransizioni potate", f"{archi_post_potatura - archi_pre_potatura}")
        Log.new("\tStati dopo la potatura", f"{nodi_post_potatura}")
        Log.new("\tTransizioni dopo la potatura", f"{archi_post_potatura}")

        # Inizializza il numero univoco dei nodi
        counter = 0
        # Rinomina i nodi non potati
        for nodo in self.nodi:
            nodo.nome = str(counter)
            counter = counter + 1

        # Verifica che il nodoIniziale sia ancora presente nello spazio comportamentale
        self.nodoIniziale = self.ricercaNodo(self.nodoIniziale)

        # Verifichiamo se ci sono nodi nello spazio comportamentale, in questo caso la potatura è stata totale e
        # potrebbe essere indice di un problema
        if not self.nodi or not self.archi:
            messaggio = "La potatura ha generato uno Spazio Comportamentale vuoto. Verificare gli input."
            Log.new("potaturaRidenominazione, ValueError", messaggio)
            raise ValueError(messaggio)

    def trovaSerieArchi(self) -> List[Arco]:
        """
        Ricerca di una sequenza "obbligata" di archi,
        senza possibili bivi al suo interno (ovvero una serie).
        :return: una serie di archi all'interno di questo SpazioComportamentale
        """
        # Inizializzo la sequenza in modo da darle lo scope corretto
        sequenza = []

        # Cerco e compilo una sequenza obbligata nello sc
        # (la prima che trovo a partire dal nodo iniziale ni)
        ni: Nodo
        for ni in self.nodi:
            t: Arco
            for t in ni.archiUscenti:
                sequenza = []
                while t is not None:
                    if len(t.nodo1.archiUscenti) == 1:
                        # verifico se ci sono più di due archi entranti in nodo1[t]
                        # metto questa verifica nell'if per risparmiare calcoli inutili
                        # (mi interessa che ci sia un solo arco entrante in nodo1[t])
                        numeroArchiEntranti = 0
                        a: Arco
                        for a in self.archi:
                            if a.nodo1 is t.nodo1:
                                numeroArchiEntranti += 1
                            if numeroArchiEntranti > 1:
                                break

                        # Se anche gli archi entranti sono uguali a 1 procedo
                        if numeroArchiEntranti == 1:
                            sequenza.append(t)
                            t = t.nodo1.archiUscenti[0]
                        else:
                            # sono giunto ad un nodo di fine sequenza con più entrate
                            sequenza.append(t)
                            t = None
                        # fine if lunghezza archi entranti
                    else:
                        # siamo di fronte a un nodo di fine sequenza con più uscite
                        # o quando siamo di fronte a un nodo di fine sequenza con 0 uscite
                        if sequenza:
                            sequenza.append(t)
                        t = None
                    # fine if sulla lunghezza degli archi uscenti
                # fine del while che compone la sequenza
                # Se ho già trovato una sequenza, non esploro più un altro arco del nodo di partenza
                if len(sequenza) >= 2:
                    return sequenza
            # fine del for sugli archi uscenti da ni
        # fine del for sui nodi dello sc quando non ho trovato una sequenza
        return []

    def trovaParalleloArchi(self) -> List[Arco]:
        """
        Ricerca di un parallelo di archi fra due nodi nello Spazio Comportamentale
        :return: una lista di archi paralleli
        """
        parallelo = []
        n: Nodo
        for n in self.nodi:
            # Inizializzo la lista di nodi adiacenti ad n osservati
            nodiOsservati = []
            a: Arco
            for a in n.archiUscenti:
                if a.nodo1 in nodiOsservati:
                    # Abbiamo trovato un nodo che si ripete fra quelli adiacenti a n
                    # quindi compiliamo il parallelo e ritorniamolo
                    b: Arco
                    for b in n.archiUscenti:
                        if b.nodo1 is a.nodo1:
                            parallelo.append(b)
                    # Ho trovato degli archi paralleli, quindi li ritorno
                    return parallelo
                # Ho osservato un nodo nuovo fra quelli adiacenti a n
                nodiOsservati.append(a.nodo1)
        # Non ho trovato dei paralleli, ritorno la lista vuota
        return parallelo

    def setAllIsPotato(self, isPotato) -> None:
        """
        Imposta il flag isPotato di tutti gli archi e i nodi dello Spazio Comportamentale
        al valore isPotato dato in input.

        :param isPotato: il valore a cui settare gli archi e i nodi
        """
        for arco in self.archi:
            arco.isPotato = isPotato
        for nodo in self.nodi:
            nodo.isPotato = isPotato

    def debugPrintDotGraph(self, debug_on, debug_path):
        """
        Stampa lo spazio comportamentale nella cartella degli output di debug, se il debug è attivo
        :param debug_on: True se il debug è attivo
        """
        if debug_on:
            Main.printDotGraph(self.makeDotGraph(),
                               f"{debug_path}/{str(SpazioComportamentale.debug_counter).zfill(4)}_expreg")
            SpazioComportamentale.debug_counter += 1

    def espressioneRegolare(self, debug_on=False, debug_path="") -> str:
        """
        Genera la diagnosi (espressione regolare) relativa a uno SpazioComportamentale semplificando archi in serie,
        in parallelo e cappi.
        :param debug_on: True per generare informazioni di debug (stampa i grafi ad ogni iterazione)
        :return: L'espressione regolare è la stringa di rilevanza dell'unico arco rimasto dopo la semplificazione
        """
        # Cloniamo questo Spazio Comportamentale nell'automa scN
        # Questa clonazione è una copia deep poiché le operazioni seguenti romperebbero i legami fra archi e nodi
        # dello spazio comportamentale corrente.
        scN = copy.deepcopy(self)

        # Definisco un nuovo nodo iniziale n0, un nuovo nodo finale nq per scN
        n0 = scN.nodoIniziale  # inizialmente è pari al nodo iniziale di scN
        nq = None

        # Verifichiamo se nel nodo iniziale sono presenti archi entranti
        esisteTransizioneEntranteANodoIniziale = False
        for arco in scN.archi:
            if arco.nodo1 is scN.nodoIniziale:
                esisteTransizioneEntranteANodoIniziale = True
                break

        # Se abbiamo trovato un arco entrante nel nodo iniziale
        # creiamo un nuovo nodo iniziale n0 ed un arco con
        # etichette nulle da n0 al nodo iniziale di scN
        if esisteTransizioneEntranteANodoIniziale:
            # Creiamo il nodo n0, nodo iniziale di scN
            n0 = Nodo()
            n0.nome = "n0"
            n0.isPotato = False
            n0.isFinale = False

            # Creiamo l'arco da n0 al vecchio nodoIniziale
            a0 = Arco(n0, scN.nodoIniziale, transizione=None, rilevanza="", osservabilita="")
            a0.isPotato = False

            # Aggiungiamo a scN il nodo n0 e l'arco a0
            scN.addNodo(n0)
            scN.addArco(a0)

        # Verifichiamo se ci sono più stati di accettazione
        # Creiamo una lista di stati di accettazione
        statiAccettazione = [n for n in scN.nodi if n.isFinale]

        # Esiste una transizione uscente dall'unico stato di accettazione?
        # Se esistono più stati di accettazione o esiste
        # una transizione uscente dall'unico stato di accettazione...
        if len(statiAccettazione) > 1 or (len(statiAccettazione) == 1 and len(statiAccettazione[0].archiUscenti) >= 1):
            # Vogliamo che l'unico stato di accettazione/nodo finale sia nq
            for nodo in statiAccettazione:
                nodo.isFinale = False

            # Inizializziamo nq, nodo finale di scN
            nq = Nodo()
            nq.nome = "nq"
            nq.isPotato = False
            nq.isFinale = True

            # Aggiungiamo a scN il nodo nq
            scN.addNodo(nq)

            # Creiamo un arco (eps-transizione) da ciascuno stato di
            # accettazione di scN al nuovo nodo finale nq
            for n in statiAccettazione:
                aq = Arco(n, nq, None, "", "")
                aq.isPotato = False
                # Aggiungiamo a scN l'arco costruito
                scN.addArco(aq)
        else:
            # Altrimenti lo stato finale nq è l'unico stato di accettazione
            nq = statiAccettazione[0]
        # Fine della creazione degli stati unici n0 e nq

        # DEBUG
        # Stampo il grafo a seguito della generazione dei nodi n0 e nq
        scN.debugPrintDotGraph(debug_on, debug_path)
        # /DEBUG

        # Definizione dell'espressione regolare
        while len(scN.archi) > 1:
            # Esiste una serie di archi fra due nodi?
            serie = scN.trovaSerieArchi()
            # se la serie non è vuota
            if serie:
                # Sostituire la serie con l'arco <n,strRilevanza,n'>
                # Definisco la stringa di rilevanza
                strRilevanza = SpazioComportamentale.componiStrRilevanzaSerie(serie)

                # Tengo traccia dei nodi iniziale e finale della serie
                nodoInizioSerie = serie[0].nodo0
                nodoFineSerie = serie[-1].nodo1

                # Resettiamo isPotato per tutti gli archi e tutti i nodi di scN
                scN.setAllIsPotato(False)

                # Indichiamo come da potare da scN tutti gli archi presenti nella serie
                # e tutti i nodi nella serie eccetto il primo e l'ultimo
                for arco in serie:
                    arco.isPotato = True
                    if arco.nodo1 is not nodoFineSerie:
                        arco.nodo1.isPotato = True

                # DEBUG
                # Stampo il grafo prima della potatura
                scN.debugPrintDotGraph(debug_on, debug_path)
                # /DEBUG

                # Elimino nodi e archi indicati come isPotato == True
                scN.potatura()

                # Creo il nuovo arco che sostituisce la serie potata, e lo aggiungo
                scN.addArco(Arco(nodoInizioSerie, nodoFineSerie, None, strRilevanza, osservabilita=""))
            # Fine analisi serie

            else:
                # Non c'è la serie. Esistono archi paralleli fra due nodi?
                parallelo = scN.trovaParalleloArchi()
                if parallelo:
                    # Sostituzione del parallelo di archi con un solo arco
                    # Resettiamo isPotato per tutti gli archi e tutti i nodi di scN
                    scN.setAllIsPotato(False)

                    # Definisco la stringa di rilevanza e marchio isPotato sugli archi del parallelo
                    strRilevanza = SpazioComportamentale.componiStrRilevanzaParallelo(parallelo)
                    t: Arco
                    for t in parallelo:
                        t.isPotato = True

                    # DEBUG
                    # Stampo il grafo prima della potatura
                    scN.debugPrintDotGraph(debug_on, debug_path)
                    # /DEBUG

                    # Creiamo l'arco che sostituisce il parallelo e lo introduciamo in scN
                    a = Arco(parallelo[0].nodo0, parallelo[0].nodo1, None, strRilevanza, osservabilita="")
                    a.isPotato = False
                    scN.addArco(a)

                    # Potiamo solo gli archi segnati come isPotato (i nodi restano inalterati)
                    # NOTA: questa è una scelta di efficienza, perché non ci sono nodi da potare
                    scN.potaturaArchi()
                # Fine analisi parallelo

                else:
                    # Non c'è neanche il parallelo.
                    # Esiste un nodo intermedio con tanti archi in/out e dei cappi?

                    # Resettiamo isPotato per tutti gli archi e tutti i nodi di scN
                    scN.setAllIsPotato(False)

                    # Definisco la stringa di rilevanza
                    strRilevanza = ""

                    # Peschiamo un nodo intermedio, né iniziale né finale
                    nodoIntermedio = None
                    for nodo in scN.nodi:
                        if nodo is not n0 and nodo is not nq:
                            nodoIntermedio = nodo
                            break

                    # Se tale nodo  intermedio esiste, studiamo i suoi cappi
                    if nodoIntermedio is not None:
                        # Esiste un cappio su nodoIntermedio? Lo rintraccio
                        cappio = None
                        k: Arco
                        for k in nodoIntermedio.archiUscenti:
                            if k.nodo1 is nodoIntermedio:
                                cappio = k
                                break

                        # Marchiamo il nodoIntermedio come da potare
                        nodoIntermedio.isPotato = True

                        # DEBUG
                        # Stampo il grafo prima della potatura
                        scN.debugPrintDotGraph(debug_on, debug_path)
                        # /DEBUG

                        # Ora posso rimuovere nodoIntermedio e tutti i suoi vecchi archi entranti e uscenti
                        # Ciclo sugli archi entranti a nodoIntermedio, eccetto i cappi
                        arcoEntrante: Arco
                        for arcoEntrante in scN.archi:
                            if arcoEntrante.nodo1 is nodoIntermedio and arcoEntrante.nodo0 is not nodoIntermedio:
                                # Ciclo sugli archi uscenti da nodoIntermedio, eccetto i cappi
                                arcoUscente: Arco
                                for arcoUscente in nodoIntermedio.archiUscenti:
                                    if arcoUscente.nodo1 is not nodoIntermedio:
                                        # Costruisco la stringa di rilevanza tenendo conto dell'eventuale cappio
                                        strRilevanzaFinale = SpazioComportamentale.componiStrRilevanzaNodoIntermedio(
                                            arcoEntrante, cappio, arcoUscente)
                                        # Per ciascuna coppia di archi entrante/uscente su nodoIntermedio
                                        # inseriamo un nuovo arco che tenga conto della presenza o meno di
                                        # un cappio su nodoIntermedio
                                        a = Arco(nodo0=arcoEntrante.nodo0, nodo1=arcoUscente.nodo1, transizione=None,
                                                 rilevanza=strRilevanzaFinale, osservabilita="")
                                        a.isPotato = False
                                        # Introduco il nuovo arco
                                        scN.addArco(a)
                                    # Fine If coppia di archi su nodoIntermedio (non cappio)
                        # Ora posso rimuovere nodoIntermedio e tutti i suoi vecchi archi entranti e uscenti
                        scN.potatura()
                    # Fine if nodoIntermedio is not none
                # Fine analisi nodo intermedio/cappi
            # Fine analisi parallelo e nodo intermedio/cappi
        # Fine while costruzione espressione regolare
        # DEBUG
        # Stampo il grafo
        scN.debugPrintDotGraph(debug_on, debug_path)
        # Resetto il debug counter
        SpazioComportamentale.debug_counter = 1
        # /DEBUG

        # L'espressione regolare è la stringa di rilevanza
        # dell'unico arco rimasto in scN
        return scN.archi[0].rilevanza

    def generaChiusuraSilenziosaDecorata(self, nodoIngresso: Nodo) -> None:
        """
        Genera una chiusura silenziosa decorata a partire dallo spazio comportamentale ed uno stato d'ingresso
        per la chiusura.
        Una chiusura silenziosa è il sottospazio dello Spazio Comportamentale contenente tutti e soli i nodi
        raggiungibili a partire da nodoIngresso attraverso cammini di archi non osservabili.
        Dopo l'esecuzione, la chiusura sarà associata all'attributo chiusura di nodoIngresso

        :param nodoIngresso: il nodo dello spazio comportamentale da cui partire per ricavare la chiusura silenziosa
        """
        # Inizializzo la chiusura
        nodoIngresso.chiusura = Chiusura()
        nodoIngresso.chiusura.addNodo(nodoIngresso)
        nodoIngresso.chiusura.nodoIniziale = nodoIngresso

        # Inizializzo la pila di nodi da esplorare
        nodiDaEsplorare = [nodoIngresso]

        # Scorriamo i nodi da esplorare
        while nodiDaEsplorare:
            nodoCorr = nodiDaEsplorare.pop()
            # Inizializzo i flag per vedere se è d'uscita/d'accettazione
            isUscita = False
            isAccettazione = nodoCorr.isFinale

            # Esploriamo gli archi uscenti del nodoCorr
            a: Arco
            for a in nodoCorr.archiUscenti:
                if a.osservabilita == "":
                    # Se l'arco è non osservabile aggiungiamo l'arco alla chiusura
                    # NOTA: usiamo append(a) per non andare a rovinare le liste di adiacenza
                    nodoIngresso.chiusura.archi.append(a)
                    # Se il nodo di destinazione non è già nella chiusura lo aggiungiamo
                    if a.nodo1 not in nodoIngresso.chiusura.nodi:
                        nodoIngresso.chiusura.addNodo(a.nodo1)
                        nodiDaEsplorare.append(a.nodo1)
                else:
                    # Se l'arco è osservabile nodoCorr è anche nodo d'uscita e di accettazione
                    isUscita = True
                    isAccettazione = True

            # Decidiamo se aggiungere nodoCorr anche ai nodi di uscita/di accettazione della chiusura
            if isUscita:
                nodoIngresso.chiusura.nodiUscita.append(nodoCorr)
            if isAccettazione:
                nodoIngresso.chiusura.nodiAccettazione.append(nodoCorr)
        # Fine while sui nodi da esplorare

        # Chiamata ad EspressioniRegolari su chiusura per decorare gli stati d'uscita
        nodoIngresso.chiusura.espressioniRegolari()

    @staticmethod
    def concatenaRilevanza(base: str, aggiunta: str):
        """
        Data una stringa base e una stringa di aggiunta, le concatena secondo la regola di concatenazione delle expreg.
        :param base: la stringa base
        :param aggiunta: la stringa da aggiungere
        :return: la concatenazione delle due stringhe
        """
        # Estraggo le alternative descritte nelle due stringhe
        alt_base = SpazioComportamentale.estraiAlternative(base)
        alt_aggiunta = SpazioComportamentale.estraiAlternative(aggiunta)

        # Creo una lista combinata di alternative che applichi la proprietà distributiva
        # tenendo conto delle stringhe vuote (ε)
        alternative = []
        for ab in alt_base:
            if ab == "ε":
                ab = ""
            for aa in alt_aggiunta:
                if aa == "ε":
                    aa = ""
                res = ab + aa
                if res == "":
                    res = "ε"
                alternative.append(res)
        alternative = set(alternative)

        # Ritorno la combinazione corretta di alternative
        if len(alternative) == 1:
            unica = alternative.pop()
            if unica == "ε":
                return ""
            else:
                return unica
        return "|".join(alternative)

    @staticmethod
    def estraiAlternative(expreg: str) -> List[str]:
        """
        Data un'espressione regolare, estrae la lista di espressioni in alternativa (ed eventualmente toglie le parentesi)
        :param expreg: un'espressione regolare
        :return: la lista di espressioni in alternativa
        """
        alternative = []

        # Controlla se l'alternativa è una stringa vuota
        if expreg == "" or expreg == "ε":
            return ["ε"]

        # Contatore parentesi
        par = 0
        # buffer da analizzare (una alternativa)
        buffer = ""
        for c in expreg:
            if c == "|" and par == 0:
                # aggiungiamo il buffer alla lista di alternative
                alternative.append(buffer)
                # resettiamo il buffer
                buffer = ""
            elif c == "(":
                par += 1
                buffer += c
            elif c == ")":
                par -= 1
                buffer += c
            else:
                buffer += c

        # Aggiungo alle alternative il residuo del buffer
        # (ipotizzo che in un'alternativa non compaia mai "" ad indicare l'alternativa vuota, piuttosto che epsilon)
        if buffer != "":
            alternative.append(buffer)

        # Compongo la lista di alternative e la ritorno
        return list(set(alternative))

    @staticmethod
    def rimuoviParentesi(expreg: str) -> str:
        # todo: da non includere nello pseudocodice, è inutilizzato
        """
        Riceve in ingresso una stringa di expreg e, se ha parentesi inutili attorno a se, le rimuove
        :param expreg: una stringa di expreg
        :return: input senza le parentesi se possibile, altrimenti l'input originale
        """
        # Le parentesi vanno tolte quando
        # - expreg ha parentesi a inizio e fine
        # e
        # - expreg senza parentesi ha un bilancio delle parentesi pari a 0

        if expreg[0] == '(' and expreg[-1] == ')':
            inner = expreg[1:-1]
            # se la stringa inizia e finisce con una parentesi
            # fai il bilancio delle parentesi fra la coppia di parentesi più esterne
            par = 0
            for c in expreg[1:-1]:
                if c == "(":
                    par += 1
                elif c == ")":
                    par -= 1
            # se il bilancio di parentesi aperte e chiuse è 0, ritorna la parte interna
            if par == 0:
                return inner
        # In caso non ci siano le condizioni per l'analisi delle parentesi, ritorna l'espressione regolare originale
        return expreg

    @staticmethod
    def alternativaRilevanza(base: str, aggiunta: str) -> str:
        """
        Data una stringa base e una stringa di aggiunta, compone l'alternativa delle due stringhe
        :param base: la stringa base
        :param aggiunta: la stringa di aggiunta
        :return: la coppia (base, hasEps) aggiornate, con base come alternativa di base e aggiunta
        """

        # IDEA:
        # 1 trasformare base e aggiunta in liste di alternative
        # 2 inserire in una lista tutte le alternative, ma senza duplicati (tipo set union)
        # 3 compilare la lista in una stringa di alternativa classica

        alt_base = SpazioComportamentale.estraiAlternative(base)
        alt_aggiunta = SpazioComportamentale.estraiAlternative(aggiunta)
        alternative = set(alt_base).union(set(alt_aggiunta))

        # Ritorno la combinazione corretta di alternative
        if len(alternative) == 1:
            unica = alternative.pop()
            if unica == "ε":
                return ""
            else:
                return unica

        return "|".join(alternative)

    @staticmethod
    def componiStrRilevanzaSerie(serie: List[Arco]) -> str:
        """
        A partire dalla serie in ingresso (una lista di Arco) considerata
        genera la stringa di rilevanza corrispondente
        :param serie: la lista di archi in serie da cui ricavare la stringa di rilevanza
        :return: la stringa di rilevanza della serie
        """
        strRilevanza = ""
        for t in serie:
            strRilevanza = SpazioComportamentale.concatenaRilevanza(strRilevanza, t.rilevanza)
        return strRilevanza

    @staticmethod
    def componiStrRilevanzaParallelo(parallelo: List[Arco]) -> str:
        """
        A partire dal parallelo in ingresso (una lista di Arco) considerato
        genera la stringa di rilevanza corrispondente
        :param parallelo: la lista di archi in parallelo da cui ricavare la stringa di rilevanza
        :return: la stringa di rilevanza del parallelo
        """
        if len(parallelo) == 1:
            return parallelo[0].rilevanza
        else:
            # Genero l'insieme di alternative presenti in tutti i rami del parallelo
            alternative = []
            for p in parallelo:
                alternative += SpazioComportamentale.estraiAlternative(p.rilevanza)
            alternative = set(alternative)

            # Ritorno la combinazione corretta di alternative
            if len(alternative) == 1:
                unica = alternative.pop()
                if unica == "ε":
                    return ""
                else:
                    return unica
            return "|".join(alternative)

    @staticmethod
    def componiStrRilevanzaNodoIntermedio(entrante: Arco, cappio: Arco, uscente: Arco) -> str:
        """
        A partire da tre archi su un nodo (uno entrante, un cappio, uno uscente)
        genera la stringa di rilevanza corrispondente
        :param entrante: l'arco entrante al nodo intermedio
        :param cappio: l'eventuale cappio sul nodo intermedio
        :param uscente: l'arco uscente dal nodo intermedio
        :return: la stringa di rilevanza sostitutiva del nodo intermedio
        """
        # Estraggo le alternative dell'arco entrante
        if entrante is not None:
            alt_entrante = SpazioComportamentale.estraiAlternative(entrante.rilevanza)
        else:
            alt_entrante = []

        # Se il cappio non è nullo, genero la sua etichetta
        if cappio and cappio.rilevanza != "" and cappio.rilevanza != "ε":
            ril_cappio = f"({cappio.rilevanza})*"
        else:
            ril_cappio = ""

        # Estraggo le alternative dell'arco uscente
        if uscente is not None:
            alt_uscente = SpazioComportamentale.estraiAlternative(uscente.rilevanza)
        else:
            alt_uscente = []

        # Distribuisco le alternative dell'arco entrante (concatenate col cappio)
        # lungo quelle dell'arco uscente tenendo conto delle stringhe vuote (ε)
        alternative = []
        for ae in alt_entrante:
            if ae == "ε":
                ae = ""
            for au in alt_uscente:
                if au == "ε":
                    au = ""
                res = ae + ril_cappio + au
                if res == "":
                    res = "ε"
                alternative.append(res)
        # Creo un set a partire dalle alternative per rimuovere i duplicati
        alternative = set(alternative)

        # Ritorno la combinazione corretta di alternative
        if len(alternative) == 1:
            unica = alternative.pop()
            if unica == "ε":
                return ""
            else:
                return unica
        return "|".join(alternative)

    def generaDiagnosticatore(self):
        """
        A partire da uno spazio comportamentale genera un Diagnosticatore
        Precondizione: lo Spazio Comportamentale sul quale il metodo viene chiamato è popolato
        Postcondizione: viene generato un diagnosticatore, ovvero uno Spazio Comportamentale ove
            - ad ogni nodo corrisponde una chiusura con la sua diagnosi,
            - ad ogni arco corrisponde un arco osservabile di sc uscente dalla chiusura, etichettato con la sua
              osservabilità e come rilevanza la concatenazione della sua rilevanza e la decorazione del nodo di uscita
              della chiusura.

        :return: il Diagnosticatore corrispondente a questo spazio comportamentale
        """
        # Costruiamo il diagnosticatore d
        d = Diagnosticatore()

        # Trova tutti i possibili nodi di ingresso delle chiusure
        # Un nodo d'ingresso della chiusura è
        # - o il nodo iniziale di sc
        # - o un nodo di sc avente almeno una transizione osservabile entrante

        # Inizializzo la lista di nodi di ingresso
        nodiIngresso: List[Nodo]
        nodiIngresso = [self.nodoIniziale]
        # Cerco tutti i nodi di sc con almeno un arco osservabile entrante O(V*V*E) = O(V**4)
        # Scorro tutti i nodi
        for n in self.nodi:
            # Guardo i suoi archi adiacenti
            for a in n.archiUscenti:
                # Se l'arco non è osservabile, passo all'arco successivo
                if a.osservabilita == "":
                    continue
                # Altrimenti, se il nodo di destinazione dell'arco osservabile non è in nodiIngresso
                # Aggiungo il nodo di destinazione a nodiIngresso
                if a.nodo1 not in nodiIngresso:
                    nodiIngresso.append(a.nodo1)
            # fine ciclo sugli archi uscenti di n
        # fine ciclo sui nodi di sc

        # Per ogni nodo di ingresso genera la chiusura e il nodo corrispondente
        # dello d (spazio chiusure)
        ni: Nodo
        for ni in nodiIngresso:
            self.generaChiusuraSilenziosaDecorata(ni)
            # Genero un nuovo nodo xn in d corrispondente alla chiusura
            xn = Nodo()
            xn.nome = 'x' + ni.nome
            xn.isPotato = False

            # Il nodo xn è finale se e solo se la sua chiusura ha una diagnosi non nulla
            # Nota: anche se ha una diagnosi con stringa vuota è finale
            xn.isFinale = ni.chiusura.diagnosi is not None

            # Associo alla chiusura del nodo xn la chiusura del suo nodo di ingresso
            xn.chiusura = ni.chiusura

            # Se il nodo generato ha una chiusura corrispondente al nodoIniziale dello sc,
            # il nodo generato è anche nodoIniziale di d
            if ni is self.nodoIniziale:
                d.nodoIniziale = xn

            # Aggiungiamo il nuovo nodo xn a d
            d.addNodo(xn)

        # Genera gli archi tra i nodi di d
        # Per ogni nodo x dello spazio delle chiusure
        x: Nodo
        for x in d.nodi:
            # Per ogni nodo di uscita della chiusura di x
            nu: Nodo
            for nu in x.chiusura.nodiUscita:
                # Per ogni arco a1 osservabile uscente da nu
                a1: Arco
                for a1 in nu.archiUscenti:
                    if a1.osservabilita != "":
                        # cerchiamo nello spazio delle chiusure,
                        # il nodo y la cui chiusura ha nodo iniziale nodo1 di a1
                        y: Nodo
                        for y in d.nodi:
                            if a1.nodo1 is y.chiusura.nodoIniziale:
                                # creiamo l'arco a2 dal nodo x corrente
                                # al nodo y dello spazio delle chiusure
                                a2 = Arco(nodo0=x, nodo1=y, transizione=a1.transizione,
                                          rilevanza=a1.rilevanza + x.chiusura.decorazioni.get(id(nu), ""),
                                          osservabilita=a1.osservabilita)
                                a2.isPotato = False
                                d.addArco(a2)

        # Ritorna lo spazio delle chiusure generato, che ormai è un diagnosticatore
        return d

    def makeDotGraph(self) -> str:
        """
        Genera la rappresentazione in formato DOT dello SpazioComportamentale, visualizzabile tramite GraphViz.
        :return: la rappresentazione in formato DOT dello SpazioComportamentale
        """
        nodi = "start[shape=\"circle\"]"
        archi = f"start\t->\tn{self.nodoIniziale.nome}"

        n: Nodo
        for n in self.nodi:
            stati = " ".join([stato.nome for stato in n.stati])
            links = " ".join(str(link) for link in n.contenutoLink)
            finale = ' peripheries=2' if n.isFinale else ''
            potato = " color=red" if n.isPotato else ""
            # Compilo i nodi
            nodi += f"\n\tn{n.nome} [label=<<b>{n.nome}</b><br/>{stati} {links}<br/>Ind. Oss.: {n.indiceOsservazione}>{finale}{potato}]"
            a: Arco
            for a in n.archiUscenti:
                transizione = "<br/>" + a.transizione.nome if a.transizione else ''
                osservabilita = f"<br/><font color=\"green4\">{a.osservabilita}</font>" if a.osservabilita != "" else ""
                rilevanza = f"<br/><font color=\"red\">{a.rilevanza}</font>" if a.rilevanza != "" else ""
                potato = " color=red" if a.isPotato else ""
                # Compilo gli archi
                archi += f"\n\tn{n.nome}\t->\tn{a.nodo1.nome} [label=<{transizione}{osservabilita}{rilevanza}>{potato}]"

        # Compilo l'output
        out = f"""digraph SpazioComportamentale {{
    // ARCHI
    {archi}

    // NODI
    {nodi}
}}
"""
        return out

    def logStats(self):
        """
        Genera delle statistiche su questo Spazio Comportamentale e le salva nel Log
        """
        Log.new("Statistiche sullo Spazio Comportamentale", "")
        Log.new("\tNumero stati", f"{len(self.nodi)}")
        Log.new("\tNumero stati finali", f"{len([n for n in self.nodi if n.isFinale])}")
        Log.new("\tNumero transizioni", f"{len(self.archi)}")


class Chiusura(SpazioComportamentale):
    """
    Classe che descrive una chiusura silenziosa decorata di uno SpazioComportamentale.
    Una chiusura silenziosa è un particolare spazio comportamentale, associato ad uno stato di uno spazio
    comportamentale di dimensione maggiore, tale da contenere tutti e soli gli stati raggiungibili attraverso
    cammini contenenti transizioni non osservabili (silenziose).

    Lo stato di partenza è detto d'ingresso della chiusura.

    A ogni stato (nodo) finale della chiusura è associata una decorazione che rappresenta l'espressione regolare di
    rilevanza relativa a tutti i cammini che portano dallo stato d'ingresso della chiusura allo stato finale.
    """
    def __init__(self):
        self.nodiUscita: List[Nodo]
        self.nodiUscita = []

        self.nodiAccettazione: List[Nodo]
        self.nodiAccettazione = []

        self.nodiAccettazione: Dict[Nodo, str]
        self.decorazioni = {}

        self.diagnosi: str
        self.diagnosi = None
        super().__init__()

    def esistonoPiuArchiStessoPedice(self, pedici: Dict[int, Nodo]) -> bool:
        """
        Data la chiusura in ingresso ed il dizionario dei pedici,
        ritorna True se esistono più archi marchiati dallo stesso pedice.
        Precondizioni:
            - I pedici corrispondono ai nodi di accettazione
            - Un arco non nel dizionario dei pedici ha sicuramente pedice None
            - Un arco con pedice None non è nel dizionario
            - Il tipo di pedici è Dict[id(Arco), Nodo], con Arco e Nodo appartenenti a chiusura,
              mentre Nodo è un nodo di accettazione per la chiusura
        :param pedici: il dizionario dei pedici (tipo: Dict[int,Nodo], il primo int è un id di un Arco)
        :return: True se esistono più archi marchiati dallo stesso pedice, False altrimenti
        """

        # Gli archi hanno lo stesso pedice anche se il loro pedice è None:
        if not pedici:
            # Caso limite: il dizionario dei pedici è vuoto
            if len(self.archi) > 1:
                # Tutti gli archi hanno pedice None
                return True
            else:
                # C'è un solo arco, con pedice None
                return False

        else:
            # Ammettiamo di avere archi con pedice non None
            # Se il dizionario dei pedici non è vuoto
            # verifico se ci sono più archi con pedice None
            if len(self.archi) - len(pedici) > 1:
                return True
            else:
                # Se non ci sono più archi con pedice None:
                # uso un dizionario per tenere traccia del numero
                # di occorrenze di ciascun nodo di accettazione
                count = {}
                for n in self.nodiAccettazione:
                    count[id(n)] = 0
                pass

            # Facciamo scorrere i nodi di accettazione per contare le occorrenze
            for entry in pedici:
                # Incremento il value del contatore relativo al pedice
                count[id(pedici[entry])] += 1
                if count[id(pedici[entry])] > 1:
                    return True

            # Se a fine ciclo non abbiamo mai tornato True,
            # ci sono più archi ma ogni arco ha pedice diverso
            return False

    def trovaParalleloArchiStessoPedice(self, pedici: Dict[int, Nodo]) -> List[Arco]:
        """
        Controllo esistenza di un insieme [<n,r1,n'>,<n,r2,n'>,...,<n,rk,n'>] di archi
        paralleli uscenti dallo stato n e diretti allo stato n',
        tutti aventi lo stesso pedice o nessun pedice.

        :param pedici: il dizionario dei pedici della chiusura, che associa agli indici degli archi
                       il nodo di accettazione pedice
        :return: l'insieme di archi paralleli con lo stesso pedice
        """
        parallelo = []
        for n in self.nodi:
            # Voglio trovare due archi con lo stesso nodo finale e lo stesso pedice
            # Inizializzo il dizionario di nodi adiacenti ad n osservati
            # associati al pedice dell'arco su cui li abbiamo reperiti
            nodiOsservati = []
            for a in n.archiUscenti:
                # Inizializzo il pedice di a (per evitare errori di chiave)
                pedice_a = pedici.get(id(a), None)

                # Ho già osservato il nodo1 di a con questo pedice?
                if (a.nodo1, pedice_a) in nodiOsservati:
                    # Abbiamo trovato un nodo che si ripete fra quelli adiacenti a n con lo stesso pedice
                    # quindi compiliamo il parallelo e ritorniamolo
                    for b in n.archiUscenti:
                        # Inizializzo il pedice di b (per evitare errori di chiave)
                        pedice_b = pedici.get(id(b), None)

                        # Se la destinazione e il pedice di a e b sono gli stessi, compilo il parallelo
                        if b.nodo1 is a.nodo1 and pedice_b is pedice_a:
                            parallelo.append(b)
                    # Ho trovato degli archi paralleli, quindi li ritorno
                    return parallelo
                else:
                    # Ho osservato un nodo nuovo fra quelli adiacenti a n
                    nodiOsservati.append((a.nodo1, pedice_a))
            # End for. Non ho trovato dei paralleli, ritorno la lista vuota
            return parallelo

    def espressioniRegolari(self) -> None:
        """
        Calcola le decorazioni per tutti i nodi di accettazione della chiusura,
        poi determina la diagnosi della chiusura.
        I valori risultanti sono disposti negli attributi decorazioni e diagnosi.
        Se la chiusura non ha nodi finali, non può avere diagnosi e dunque la sua
        diagnosi sarà None.
        """

        # Definiamo una struttura dizionario che gestisca i pedici della chiusura
        # Il dizionario associa all'id di ciascun arco della chiusura (tipo int) un pedice (tipo Nodo), ovvero
        # il riferimento al nodo d'accettazione per cui è valida l'etichetta
        # di rilevanza.
        # - I pedici corrispondono ai nodi di accettazione
        # - Un arco non nel dizionario dei pedici ha sicuramente pedice None
        # - Un arco con pedice None non è nel dizionario
        # - Il tipo di pedici è Dict[id(Arco), Nodo]
        #   con Arco e Nodo appartenenti a chiusura
        pedici: Dict[int, Nodo]
        pedici = {}

        # Cloniamo questa Chiusura nell'automa scN
        # Questa clonazione è una copia deep poiché le operazioni seguenti romperebbero i legami fra archi e nodi
        # della chiusura corrente.
        scN = copy.deepcopy(self)

        # Ripulisco il clone della chiusura dagli archi osservabili uscenti,
        # che ancora sono nelle liste di adiacenza dei nodiUscita
        for nu in scN.nodiUscita:
            # cerchiamo archi osservabili nelle liste di archiUscenti e li rimuoviamo
            nu.archiUscenti = [a for a in nu.archiUscenti if a.osservabilita == ""]

        # Creo un dizionario che associ i riferimenti
        # ai nodi della chiusura in input ai nodi della chiusura clonata
        nodiClone2Origin: Dict[int, Nodo]
        nodiClone2Origin = {}
        for i in range(0, len(self.nodi)):
            # l'uso di i sui nodi paralleli mantiene correttamente la corrispondenza dei nodi fra la chiusura
            # e il suo clone perché le liste sono ordinate
            nodiClone2Origin[id(scN.nodi[i])] = self.nodi[i]
        # Questo ci servirà a fine esecuzione per tradurre le decorazioni
        # di scN nelle decorazioni della chiusura originale

        # Definiamo un nuovo nodo iniziale n0, un nuovo nodo finale nq
        n0 = None
        nq = None
        # Verifichiamo se nel nodo iniziale sono presenti archi entranti
        esisteTransizioneEntranteANodoIniziale = False
        for arco in scN.archi:
            if arco.nodo1 is scN.nodoIniziale:
                esisteTransizioneEntranteANodoIniziale = True
                break

        # 1:
        # Se abbiamo trovato un arco entrante nel nodo iniziale (interno alla chiusura)
        # creiamo un nuovo nodo iniziale n0 ed un arco con
        # etichette nulle da n0 al nodo iniziale di scN
        if esisteTransizioneEntranteANodoIniziale:
            # Creiamo il nodo n0, nodo iniziale di scN
            n0 = Nodo()
            n0.nome = "n0"
            n0.isPotato = False
            n0.isFinale = False

            # Creiamo l'arco da n0 al vecchio nodoIniziale
            a0 = Arco(n0, scN.nodoIniziale, transizione=None, rilevanza="", osservabilita="")
            a0.isPotato = False

            # Aggiungiamo a scN il nodo n0 e l'arco a0
            scN.addNodo(n0)
            scN.addArco(a0)
        else:
            # 4:
            n0 = scN.nodoIniziale

        # 6: Inizializziamo nq, nodo finale di scN
        nq = Nodo()
        nq.nome = "nq"
        nq.isPotato = False
        nq.isFinale = True
        # Aggiungiamo a scN il nodo nq
        scN.addNodo(nq)

        # 7-9:
        # Creiamo un arco (eps-transizione) da ciascuno stato di
        # accettazione di scN al nuovo nodo finale nq
        for n in scN.nodiAccettazione:
            aq = Arco(nodo0=n, nodo1=nq, transizione=None, rilevanza="", osservabilita="")
            aq.isPotato = False

            # Aggiungiamo a scN l'arco costruito
            scN.addArco(aq)

        # 11: ciclo principale
        while len(scN.nodi) > 2 or scN.esistonoPiuArchiStessoPedice(pedici):
            # 12: Esiste una serie di archi tra due nodi?
            serie = scN.trovaSerieArchi()

            # Verifico se la serie non ha pedici
            serie_no_pedici = True
            # E verifico se la serie ha pedice solo sull'ultimo arco
            serie_solo_ultimo_ha_pedice = True
            if serie:
                for a in serie[:-1]:
                    if id(a) in pedici:
                        serie_no_pedici = False
                        serie_solo_ultimo_ha_pedice = False
                        break
                if serie_no_pedici:
                    # Controllo l'ultimo elemento
                    if id(serie[-1]) in pedici:
                        serie_no_pedici = False
                        serie_solo_ultimo_ha_pedice = True
                    else:
                        serie_no_pedici = True
                        serie_solo_ultimo_ha_pedice = False

            # if principale per il controllo della serie
            if serie and (serie_no_pedici or serie_solo_ultimo_ha_pedice):
                # 13: Se l'ultimo nodo della serie non è nq
                # e il penultimo non è di accettazione
                # e l'ultimo arco della serie non ha pedice...
                # fine while ciclo principale

                # Tengo traccia dei nodi iniziale e finale della serie
                nodoInizioSerie = serie[0].nodo0
                nodoPenultimoSerie = serie[-1].nodo0
                nodoFineSerie = serie[-1].nodo1

                # Tengo traccia del pedice con cui etichettare la stringa
                pedice = None

                # Definisco la stringa di rilevanza (e eventualmente il suo pedice)
                strRilevanza = ""
                if serie_solo_ultimo_ha_pedice:
                    # L'ultimo arco ha pedice, righe 18-19
                    # Sostituire la serie con l'arco
                    # <nodoInizioSerie,strRilevanza(con pedice dell'ultimo arco della serie),nodoFineSerie>
                    # Compilo la stringa di rilevanza r1...r_k
                    strRilevanza = SpazioComportamentale.componiStrRilevanzaSerie(serie)

                    # Fisso il pedice della nuova etichetta
                    # a quello dell'ultimo arco della serie
                    pedice = pedici[id(serie[-1])]
                elif nodoFineSerie is not nq and nodoPenultimoSerie not in scN.nodiAccettazione:
                    # L'ultimo arco non ha pedice, righe 12-17
                    # Sostituire la serie con l'arco <nodoInizioSerie,strRilevanza,nodoFineSerie>
                    # Compilo la stringa di rilevanza r1...r_k
                    strRilevanza = SpazioComportamentale.componiStrRilevanzaSerie(serie)
                else:
                    # la fine serie è il nodo finale,
                    # o il penultimo della serie è nodo d'accettazione

                    # Sostituire la serie con l'arco <nodoInizioSerie,strRilevanza,nodoFineSerie>
                    # Definisco la stringa di rilevanza r1...r_(k-1)
                    # con k-1 indice del penultimo arco nella serie

                    # 16: Consideriamo la serie meno il penultimo elemento
                    strRilevanza = SpazioComportamentale.componiStrRilevanzaSerie(serie[0:-1])

                    # Fisso il pedice al penultimo nodo della serie
                    # che in questo caso è sempre uno stato d'accettazione
                    pedice = nodoPenultimoSerie
                # Fine definizione strRilevanza e pedice

                # Sostituzione dell'arco, righe 14:, 16:, 19:
                # Resettiamo isPotato per tutti gli archi e tutti i nodi di scN
                scN.setAllIsPotato(False)

                # Indichiamo come da potare da scN tutti gli archi presenti nella serie
                # e tutti i nodi nella serie eccetto il primo e l'ultimo
                # In questo ciclo ripuliamo anche il dizionario se l'arco da potare è presente
                # nel dizionario
                for arco in serie:
                    arco.isPotato = True
                    if arco.nodo1 is not nodoFineSerie:
                        arco.nodo1.isPotato = True

                    # Eliminiamo dal dizionario dei pedici la voce corrispondente all'arco da potare
                    if id(arco) in pedici:
                        pedici.pop(id(arco))
                # fine del for
                # Elimino nodi e archi indicati come isPotato == True
                scN.potatura()

                # Creo il nuovo arco che sostituisce la serie potata
                a = Arco(
                    nodo0=nodoInizioSerie, nodo1=nodoFineSerie, transizione=None,
                    rilevanza=strRilevanza, osservabilita="")
                a.isPotato = False

                # Introduco il nuovo arco (anche nelle liste di adiacenza)
                scN.addArco(a)

                # Fissiamo l'eventuale pedice del nuovo arco
                if pedice is not None:
                    pedici[id(a)] = pedice
            else:
                # La serie non c'è.
                # Analisi del parallelo. Righe 20-23:
                # Esiste un parallelo contenente più archi con lo stesso (o nessun) pedice?
                parallelo = scN.trovaParalleloArchiStessoPedice(pedici)

                if parallelo:
                    # Sostituzione del parallelo di archi con un solo arco
                    # Resettiamo isPotato per tutti gli archi e tutti i nodi di scN
                    scN.setAllIsPotato(False)

                    # Definisco la stringa di rilevanza
                    strRilevanza = SpazioComportamentale.componiStrRilevanzaParallelo(parallelo)

                    # Creiamo l'arco che sostituisce il parallelo
                    a = Arco(nodo0=parallelo[0].nodo0, nodo1=parallelo[0].nodo1, transizione=None,
                             rilevanza=strRilevanza, osservabilita="")
                    a.isPotato = False

                    # Introduco il nuovo arco
                    scN.addArco(a)
                    # Fissiamo l'eventuale pedice del nuovo arco
                    if id(parallelo[0]) in pedici:
                        pedici[id(a)] = pedici[id(parallelo[0])]

                    # Marchio isPotato sugli archi del parallelo
                    for t in parallelo:
                        # Definisco quali archi paralleli potare
                        t.isPotato = True
                        # Eliminiamo dal dizionario dei pedici la voce
                        # corrispondente all'arco parallelo da potare
                        if id(t) in pedici:
                            pedici.pop(id(t))

                    # Potiamo solo gli archi segnati come isPotato (i nodi restano inalterati),
                    # perché non ci sono nodi da potare
                    # NOTA: questa è una scelta di efficienza, perché non ci sono nodi da potare
                    scN.potaturaArchi()
                    # Fine analisi parallelo
                else:
                    # Il parallelo non c'è
                    # Analisi del nodo intermedio. Righe 24-48
                    # Esiste un nodo intermedio con tanti archi in/out e dei cappi?
                    # Resettiamo isPotato per tutti gli archi e tutti i nodi di scN
                    scN.setAllIsPotato(False)

                    # Definisco la stringa di rilevanza
                    strRilevanza = ""

                    # Peschiamo un nodo intermedio, né iniziale né finale
                    nodoIntermedio = None
                    for nodo in scN.nodi:
                        if nodo is not n0 and nodo is not nq:
                            nodoIntermedio = nodo
                            break

                    # Se tale nodo  intermedio esiste, studiamo i suoi cappi
                    if nodoIntermedio is not None:
                        # Marchiamo il nodoIntermedio come da potare
                        nodoIntermedio.isPotato = True
                        # Tengo traccia di quali id di archi entranti e uscenti dal nodo intermedio
                        # devo togliere dal dizionario
                        idArchiDaRimuovereDaPedici = []

                        # Esiste un cappio su nodoIntermedio? Creo la sua stringa di rilevanza
                        # NOTA: Costruire la stringa qui ci consente di risparmiare cicli
                        strRilevanzaCappio = ""
                        nodoIntermedio: Nodo
                        for cappio in nodoIntermedio.archiUscenti:
                            if cappio.nodo1 is nodoIntermedio:
                                # segno come da rimuovere dai pedici il cappio su nodoIntermedio
                                idArchiDaRimuovereDaPedici.append(id(cappio))
                                if len(cappio.rilevanza) == 1:
                                    strRilevanzaCappio = cappio.rilevanza + "*"
                                elif len(cappio.rilevanza) > 1:
                                    strRilevanzaCappio = f"({cappio.rilevanza})*"
                                break

                        # todo: verifica che accade se ci sono più cappi sullo stesso nodo con pedice diverso (tipo benchmark)

                        # Ciclo sugli archi entranti a nodoIntermedio, eccetto i cappi
                        for arcoEntrante in scN.archi:
                            if arcoEntrante.nodo1 is nodoIntermedio and arcoEntrante.nodo0 is not nodoIntermedio:
                                # segno come da rimuovere dai pedici l'arco entrante in nodoIntermedio non cappio
                                idArchiDaRimuovereDaPedici.append(id(arcoEntrante))
                                for arcoUscente in nodoIntermedio.archiUscenti:
                                    if arcoUscente.nodo1 is not nodoIntermedio:
                                        # segno come da rimuovere dai pedici l'arco uscente da nodoIntermedio non cappio
                                        idArchiDaRimuovereDaPedici.append(id(arcoUscente))
                                        # Costruisco la stringa di rilevanza tenendo conto dell'eventuale cappio
                                        strRilevanzaFinale = arcoEntrante.rilevanza \
                                                             + strRilevanzaCappio \
                                                             + arcoUscente.rilevanza

                                        # Per ciascuna coppia di archi entrante/uscente su nodoIntermedio
                                        # inseriamo un nuovo arco che tenga conto della presenza o meno di
                                        # un cappio su nodoIntermedio

                                        # Creiamo l'arco che sostituisce il nodoIntermedio
                                        a = Arco(nodo0=arcoEntrante.nodo0, nodo1=arcoUscente.nodo1, transizione=None,
                                                 rilevanza=strRilevanzaFinale, osservabilita="")
                                        a.isPotato = False

                                        # Produciamo il pedice del nuovo arco
                                        pedice = None
                                        # Riga 27: Calcolo del pedice
                                        if id(arcoUscente) in pedici:
                                            # Righe 40-46: il pedice dell'arco uscente non è NIL
                                            pedice = pedici[id(arcoUscente)]
                                        elif arcoUscente.nodo1 is nq and arcoUscente.nodo0 in scN.nodiAccettazione:
                                            # Righe 28-39:
                                            pedice = arcoUscente.nodo0

                                        # Introduco il nuovo arco
                                        scN.addArco(a)
                                        # Fissiamo l'eventuale pedice del nuovo arco
                                        if pedice is not None:
                                            pedici[id(a)] = pedice
                                    # Fine if coppia di archi su nodoIntermedio (non cappio)
                                # Fine for ricerca secondo arco (non cappio)
                        # Fine for ricerca primo arco (non cappio)
                        # Ora posso rimuovere nodoIntermedio e tutti i suoi archi entranti e uscenti
                        scN.potatura()
                        # Rimuovo anche tutti gli archi potati dal dizionario dei pedici
                        for i in idArchiDaRimuovereDaPedici:
                            if i in pedici: # si potrebbe risparmiare qualche ciclo qui eliminando i duplicati da idArchiDaRimuovereDaPedici
                                pedici.pop(i)

                    # Fine if nodoIntermedio is not None
                # Fine controllo su parallelo/nodo intermedio
            # fine controllo serie
        # fine while principale

        # Ora ci accingiamo a preparare l'uscita (righe 51-55:)
        # Decoriamo la chiusura originale
        for arco in scN.archi:
            # Verifichiamo se l'arco è decorato, quindi se il suo id è contenuto in pedici
            pedice_arco = pedici.get(id(arco), None)
            if pedice_arco:
                # Traduco il riferimento al nodo che è il pedice dell'arco, in modo da avere il nodo (pedice)
                # corrispondente nella chiusura di partenza.
                # Alla decorazione di tale nodo, per questa chiusura, associo la rilevanza dell'arco decorato
                nodo_orig = nodiClone2Origin[id(pedice_arco)]
                self.decorazioni[id(nodo_orig)] = arco.rilevanza

        # Calcoliamo anche la diagnosi della chiusura come
        # l'alternativa delle decorazioni relative agli stati finali della chiusura
        nodiFinali = [nodo for nodo in self.nodiAccettazione if nodo.isFinale]

        if nodiFinali:
            # La chiusura ha nodi finali
            strDiagnosi = ""
            for n in nodiFinali:
                strDiagnosi = SpazioComportamentale.alternativaRilevanza(strDiagnosi, self.decorazioni.get(id(n), ""))

            # Trascrivo la diagnosi nella chiusura
            self.diagnosi = strDiagnosi
        else:
            # La chiusura non ha nodi finali
            self.diagnosi = None


class Diagnosticatore(SpazioComportamentale):
    """
    Un diagnosticatore è uno SpazioComportamentale delle chiusure ai cui nodi è associata la
    Chiusura silenziosa decorata, a ciascun nodo finale è associata una diagnosi,
    ogni Arco è dotato di etichetta di osservabilità e di espressione regolare di rilevanza.
    """
    def __init__(self):
        super().__init__()

    def diagnosiLineare(self, ol: List[str]) -> str:
        """
        Calcola la diagnosi relativa ad un'osservazione lineare sfruttando questo diagnosticatore.
        Riceve in ingresso un'osservazione lineare ol, ovvero una lista di osservazioni.
        L'uscita è un'espressione regolare di rilevanza, ovvero una stringa.
        :param ol: la lista di stringhe di osservazione lineare su questo diagnosticatore
        :return: la diagnosi lineare relativa ad ol
        """
        # coppie è un dizionario che associa all'id di un nodo del diagnosticatore
        # un'espressione regolare corrispondente.
        # Viene già popolato con la coppia iniziale
        coppie = {id(self.nodoIniziale): (self.nodoIniziale, "")}

        # Ciclo sulla osservazione lineare
        for o in ol:
            # ricostruisco le coppie
            coppie_n = {}
            for k_o, (x1, r1) in coppie.items():
                for arco in x1.archiUscenti:
                    if arco.osservabilita == o:
                        # 6: Concatenazione delle etichette lungo la traiettoria
                        r2 = Diagnosticatore.concatenaRilevanza(r1, arco.rilevanza)
                        # 7: Se trova il nodo di destinazione dell'arco come chiave
                        # nelle nuove coppie, aggiorna la rilevanza di tale nodo
                        # oppure inserisce la coppia nodo dest, rilevanza
                        if id(arco.nodo1) in coppie_n:
                            coppie_n[id(arco.nodo1)] = \
                                (arco.nodo1, Diagnosticatore.alternativaRilevanza(coppie_n[id(arco.nodo1)][1], r2))
                        else:
                            coppie_n[id(arco.nodo1)] = (arco.nodo1, r2)
                        # end if
                    # end if
                # end for, fine ciclo su archi uscenti da x1
            # fine ciclo sulle coppie
            # aggiornamento coppie
            coppie = coppie_n
        # fine ciclo sulle osservazioni

        # 16: rimozione coppie dove x non è di accettazione (dunque isFinale)
        coppie = {k:(nodo, rilevanza) for k,(nodo, rilevanza) in coppie.items() if nodo.isFinale}

        # 17: se resta una sola coppia...
        ret = ""
        if len(coppie) == 1:
            # accediamo all'ultima (unica) coppia con un abuso di notazione
            # concateniamo la sua rilevanza alla diagnosi del suo nodo
            k, (x, r) = coppie.popitem()
            ret = Diagnosticatore.concatenaRilevanza(r, x.chiusura.diagnosi)
        else:
            # ci sono più coppie
            # la stringa da ritornare è l'alternativa delle concatenazioni
            # fra le stringhe di rilevanza delle coppie e le diagnosi del
            # nodo corrispondente
            # todo: crea esempio che finisca in questo caso, al momento nessuna rete finisce qui
            for k_o, (x, r) in coppie.items():
                ret = Diagnosticatore.alternativaRilevanza(
                    ret, Diagnosticatore.concatenaRilevanza(r, x.chiusura.diagnosi))

        # Ritorna la diagnosi lineare
        return ret

    def logStats(self):
        """
        Genera delle statistiche su questo Diagnosticatore e le salva nel Log
        """
        Log.new("Statistiche sul Diagnosticatore", "")
        Log.new("\tNumero stati del diagnosticatore", f"{len(self.nodi)}")
        Log.new("\tNumero stati finali del diagnosticatore", f"{len([n for n in self.nodi if n.isFinale])}")
        Log.new("\tNumero stati nelle chiusure", f"{sum([len(n.chiusura.nodi) for n in self.nodi])}")
        Log.new("\tNumero transizioni non osservabili (nelle chiusure)", f"{sum([len(n.chiusura.nodi) for n in self.nodi])}")
        Log.new("\tNumero transizioni osservabili (fra gli stati del diagnosticatore)", f"{len(self.archi)}")


## MAIN ##
class Log:
    """
    Classe statica contenente il log dell'esecuzione corrente.
    Utile per tenere traccia di informazioni sull'esecuzione dei vari algoritmi.
    """

    """
    Attributo statico che rappresenta le statistiche sull'esecuzione corrente
    """
    stats = []

    """
    Attributo statico che tiene conto di quando è stata chiamata l'ultima volta la funzione cronometro()
    """
    tempo = 0

    @staticmethod
    def print() -> str:
        """
        Genera la stringa con tutte le informazioni loggate
        :return: la
        """
        out = []
        for (k, v) in Log.stats:
            out.append(f"{k}: {v}")
        return "\n".join(out)

    @staticmethod
    def new(chiave: str, valore: str) -> None:
        """
        Inserisce una nuova entry nel log come coppia chiave valore.
        :param chiave: la descrizione dell'entry nel log
        :param valore: il valore dell'entry nel log
        """
        Log.stats.append((chiave, valore))

    @staticmethod
    def logtime(label="Timestamp") -> None:
        """
        Logga il timestamp
        """
        tempo = datetime.today().strftime("%d/%m/%Y %H:%M:%S")
        Log.new(label, tempo)

    @staticmethod
    def cronometro() -> float:
        """
        Aggiorna la variabile tempo e ritorna quanto tempo è passato dall'ultima chiamata a cronometro (senza tenere
        conto dei tempi di sleep dello scheduler di sistema).
        La prima chiamata ritorna un valore inaffidabile.
        È basato su time.process_time()
        :return
        """
        tempo_new = time.process_time()
        laptime = tempo_new - Log.tempo
        Log.tempo = tempo_new
        return laptime

    @staticmethod
    def reset() -> None:
        """
        Resetta il log ed il cronometro ad uno stato pulito.
        Utile alla fine di un compito se si pensa di eseguirne un altro subito dopo.
        """
        Log.stats = []
        Log.tempo = 0


class Main:
    """
    Classe statica contenente tutti i metodi di alto livello necessari all'interazione con l'utente
    """

    """Path di default per gli output"""
    DEFAULT_OUTPUT_PATH = "outputs/"

    """Indice della run corrente (meglio recuperarlo usando getUniqueRunID()"""
    URID = None

    @staticmethod
    def getUniqueRunID(output_path: str) -> int:
        """
        Cerca in output_path l'esistenza di un file di configurazione contenente il numero da utilizzare come ID per
        marcare i file di output in modo univoco. Se non lo trova lo crea, se lo trova lo aggiorna.
        :param output_path: il percorso di output corrente
        :return: lo unique run ID da usare per la run corrente nella cartella corrente in output
        """
        uridpath = f"{output_path}.urid"
        if Main.URID is None:
            # Se l'URID non è ancora stato inizializzato nel software
            # Controlla se il file esiste
            if os.path.isfile(uridpath):
                # Se esiste, aggiorna Main.URID e aggiorna il file
                with open(uridpath, "rb") as ufile:
                    oldurid = load(ufile)
                    Main.URID = oldurid + 1
            else:
                # Se non esiste, inizializza a 0 Main.URID
                Main.URID = 0

            # Poi aggiorna il file .urid, o lo crea se non c'è
            with open(uridpath, "wb") as ufile:
                dump(Main.URID, ufile)

        # Ora che l'URID è stato sicuramente inizializzato, lo ritorna
        return Main.URID

    @staticmethod
    def outputSerializer(nome_compito: str, rete: ReteFA, sc: SpazioComportamentale, output_path="", osservazioneLineare=None):
        """
        Genera i file di output (XML e DOT/GV) relativi alla reteFA e allo SpazioComportamentale in ingresso.
        Se possibile, renderizza lo spazio comportamentale in input mediante il tool dot di GraphViz.
        Per funzionare, GraphViz deve essere installato e dot deve essere nella PATH del sistema operativo.
        Vedi https://graphviz.org/download/ per informazioni.

        :param nome_compito: nome del compito per cui si sta generando l'output
        :param rete: la ReteFA in output
        :param sc: lo SpazioComportamentale in output
        :param output_path: percorso che punta alla cartella dove salvare l'output
        :param osservazioneLineare: l'eventuale osservazione lineare
        """

        # Logica di costruzione dei filename
        today = datetime.today()
        # unique_id = today.strftime("%Y%m%d")
        unique_id = str(Main.getUniqueRunID(output_path)).zfill(3)
        filename_xml = output_path + unique_id + "_" + nome_compito + ".xml"

        # Deduci il tipo di spazio comportamentale stampato
        # sia per il nome del file .gv e .png
        # sia per il tag da usare nell'XML per riportare la rappresentazione dot del grafo
        tipo_grafo = ""
        tag_grafo = ""
        if nome_compito == "compito1":
            tipo_grafo = "SC"
            tag_grafo = "spazioComportamentale"
        elif nome_compito == "compito2":
            tipo_grafo = "SCOL"
            tag_grafo = "spazioComportamentaleOsservazioneLineare"
        elif nome_compito == "compito4":
            tipo_grafo = "D"
            tag_grafo = "diagnosticatore"
        filename_grafo = output_path + unique_id + "_"

        # Genera l'albero XML
        root = ET.Element(nome_compito)
        t = ET.ElementTree(root)

        # Varia il comportamento a seconda della presenza o meno dell'Osservazione Lineare
        if osservazioneLineare:
            sc_elem = ET.SubElement(root, "osservazioneLineare")
            sc_elem.text = repr(osservazioneLineare)

        # Varia il comportamento a seconda della necessità di stampare o meno lo spazio
        dotgraph = None
        stampa_spazio = False
        if nome_compito == "compito1" or nome_compito == "compito2" or nome_compito == "compito4":
            # Bisogna stampare lo spazio
            stampa_spazio = True
            dotgraph = sc.makeDotGraph()

            sc_elem = ET.SubElement(root, tag_grafo)
            sc_elem.text = "\n" + dotgraph + "\n"

        commento_elem = ET.SubElement(root, "commento")
        commento_elem.text = "\n" + Log.print() + "\n"

        base64_elem = ET.SubElement(root, "base64")
        base64_elem.text = str(b64encode(dumps((rete, sc))), 'utf-8')

        with open(filename_xml, 'wb') as fileXML:
            t.write(fileXML, encoding="utf-8", short_empty_elements=False)
            if stampa_spazio:
                with open(f"{filename_grafo}{tipo_grafo}.gv", 'w', encoding="utf-8") as fileDOT:
                    fileDOT.write(dotgraph)
                    if nome_compito == "compito1":
                        with open(f"{filename_grafo}rete.gv", 'w', encoding="utf-8") as fileDOTRete:
                            fileDOTRete.write(rete.makeDotGraph())

        try:
            if stampa_spazio:
                subprocess.call(f"dot -Tpng {filename_grafo}{tipo_grafo}.gv -o {filename_grafo}{tipo_grafo}.png")
                if nome_compito == "compito1":
                    subprocess.call(f"dot -Tpng {filename_grafo}rete.gv -o {filename_grafo}rete.png")
        except Exception as fnf:
            print(fnf + "Forse graphviz non è installato ed impostato nella variabile PATH di sistema... vedi "
                      "https://graphviz.org/download/")

        # Resetta il log
        Log.reset()

    @staticmethod
    def printDotGraph(dotgraph: str, filename: str):
        """
        Stampa il grafo espresso in linguaggio dot nel file png col nome dato
        :param dotgraph: stringa rappresentante il grafo in DOT
        :param filename: path dove salvare l'immagine
        """
        with open(filename + ".gv", 'w', encoding="utf-8") as fileDOT:
            fileDOT.write(dotgraph)
        try:
            subprocess.call(f"dot -Tpng {filename}.gv -o {filename}.png")
            #os.remove(f"{filename}.gv")
        except Exception as fnf:
            print(fnf+" Forse graphviz non è installato ed impostato nella variabile PATH di sistema... vedi "
                      "https://graphviz.org/download/")


    @staticmethod
    def compito1(reteFA_xml_path: str, output_path: str) -> (ReteFA, SpazioComportamentale):
        """
        Genera gli oggetti ReteFA e SpazioComportamentale a partire da una descrizione della rete FA come file XML
        ben formattato.
        Inoltre salva su disco il file di output corrispondente nella posizione specificata in output_path (o in
        alternativa nella stessa cartella dell'input).

        :param reteFA_xml_path: il percorso su disco al file XML che descrive la ReteFa
        :param output_path: il percorso su disco dove salvare il file XML che descrive l'output di Compito1
        :return: la coppia ReteFA, SpazioComportamentale
        """
        Log.logtime()
        Log.new("Compito 1 - generazione dello Spazio Comportamentale a partire dalla rete", f"{reteFA_xml_path}")
        Log.cronometro()
        rete = ReteFA.fromXML(reteFA_xml_path)
        Log.new("\tTempo di generazione della ReteFA da XML", f"{Log.cronometro()}s")
        rete.logStats()

        Log.new("Generazione dello Spazio Comportamentale","")
        Log.cronometro()
        sc = SpazioComportamentale()
        sc.creaSpazioComportamentale(rete)
        Log.new("\tTempo di generazione dello SpazioComportamentale da ReteFA", f"{Log.cronometro()}s")
        sc.potaturaRidenominazione()
        Log.new("\tTempo di potatura dello SpazioComportamentale", f"{Log.cronometro()}s")
        sc.logStats()

        # Genera file in output
        Main.outputSerializer("compito1", rete, sc, output_path=output_path)

        return rete, sc

    @singledispatchmethod
    @staticmethod
    def compito2(reteFA, osservazioneLineare: List[str], output_path: str) -> (ReteFA, SpazioComportamentale):
        """
        Genera gli oggetti ReteFA e SpazioComportamentale relativo all'osservazione lineare data, a partire da una
        descrizione della rete FA come file XML ben formattato e un'osservazione lineare valida sulla rete FA.
        Inoltre salva su disco il file di output corrispondente nella posizione specificata in output_path (o in
        alternativa nella stessa cartella dell'input).

        :param reteFA: il percorso su disco al file XML che descrive la ReteFa
        :param osservazioneLineare: una lista ordinata di stringhe dove ogni stringa rappresenta un'osservazione su reteFA
        :param output_path: il percorso su disco dove salvare il file XML che descrive l'output di Compito 2
        :return: la coppia ReteFA, SpazioComportamentale
        """
        # Log.new("\nCompito 2 - Generazione dello Spazio Comportamentale relativo all'Osservazione lineare","")
        # Log.new("Rete FA in input XML", f"{reteFA}")
        # Log.new("Osservazione Lineare", f"{osservazioneLineare}")
        # Log.cronometro()
        # rete = ReteFA.fromXML(reteFA)
        # Log.new("\tTempo di generazione della ReteFA da XML", f"{Log.cronometro()}s")
        # rete.logStats()
        #
        # Log.new("Generazione dello SCOL", f"")
        # Log.cronometro()
        # scol = SpazioComportamentale()
        # scol.creaSpazioComportamentaleOsservazioneLineare(rete, osservazioneLineare)
        # scol.logStats()
        # Log.new("\tTempo di generazione dello Spazio Comportamentale relativo all'Osservazione Lineare da ReteFA",
        #         f"{Log.cronometro()}s")
        # scol.potaturaRidenominazione()
        # Log.new("\tTempo di potatura dello SpazioComportamentale relativo all'Osservazione Lineare", f"{Log.cronometro()}s")
        #
        # # Genera file in output
        # Main.outputSerializer("compito2", rete, sc, output_path=output_path, osservazioneLineare=osservazioneLineare)
        #
        # return rete, scol
        raise NotImplementedError("Il tipo di reteFA in input alla funzione compito2 non è valido.")

    @compito2.register(str)
    @staticmethod
    def _(reteFA: str, osservazioneLineare: List[str], output_path: str) -> (ReteFA, SpazioComportamentale):
        Log.logtime()
        Log.new("\nCompito 2 - Generazione dello Spazio Comportamentale relativo all'Osservazione lineare", "")
        Log.new("\tRete FA in input XML", f"{reteFA}")
        Log.new("\tOsservazione Lineare", f"{osservazioneLineare}")
        Log.cronometro()
        rete = ReteFA.fromXML(reteFA)
        Log.new("\tTempo di generazione della ReteFA da XML", f"{Log.cronometro()}s")
        rete.logStats()

        Log.new("Generazione dello SCOL", f"")
        Log.cronometro()
        scol = SpazioComportamentale()
        scol.creaSpazioComportamentaleOsservazioneLineare(rete, osservazioneLineare)
        scol.logStats()
        Log.new("\tTempo di generazione dello Spazio Comportamentale relativo all'Osservazione Lineare da ReteFA",
                f"{Log.cronometro()}s")
        scol.potaturaRidenominazione()
        Log.new("\tTempo di potatura dello SpazioComportamentale relativo all'Osservazione Lineare",
                f"{Log.cronometro()}s")

        # Genera file in output
        Main.outputSerializer("compito2", rete, scol, output_path=output_path, osservazioneLineare=osservazioneLineare)

        return rete, scol

    @compito2.register(ReteFA)
    @staticmethod
    def _(reteFA: ReteFA, osservazioneLineare: List[str], output_path: str) -> (ReteFA, SpazioComportamentale):
        Log.logtime()
        Log.new("\nCompito 2 - Generazione dello Spazio Comportamentale relativo all'Osservazione lineare", "")
        Log.new("Rete FA in input", f"Recuperata da una run precedente")
        Log.new("Osservazione Lineare", f"{osservazioneLineare}")

        Log.cronometro()
        scol = SpazioComportamentale()
        scol.creaSpazioComportamentaleOsservazioneLineare(reteFA, osservazioneLineare)
        Log.new("\tTempo di generazione dello Spazio Comportamentale relativo all'Osservazione Lineare da ReteFA",
                f"{Log.cronometro()}s")
        scol.potaturaRidenominazione()
        Log.new("\tTempo di potatura dello SpazioComportamentale relativo all'Osservazione Lineare",
                f"{Log.cronometro()}s")

        # Genera file in output
        Main.outputSerializer("compito2", reteFA, scol, output_path=output_path, osservazioneLineare=osservazioneLineare)

        return reteFA, scol

    @staticmethod
    def compito3(scol: SpazioComportamentale, osservazioneLineare: List[str], output_path: str, debug_on=False) -> str:
        """
        Genera la diagnosi a partire dallo SpazioComportamentale relativo all'osservazione lineare (come generato da compito2).
        Inoltre salva su disco il file di output corrispondente nella posizione specificata in output_path (o in
        alternativa nella stessa cartella dell'input).

        :param scol: lo SpazioComportamentale relativo all'osservazione lineare generato da Compito 2
        :param output_path: il percorso su disco dove salvare il file XML che descrive l'output di Compito 3
        :return: la stringa di diagnosi relativa all'osservazione lineare data sulla ReteFA
        """
        # Imposto la posizione dell'output del debug
        debug_path = output_path + "/debug"

        Log.logtime()
        Log.new("Compito 3 - Calcolo della diagnosi, a partire dallo spazio comportamentale relativo "
                "all'osservazione lineare", "")

        Log.cronometro()
        diagnosi = scol.espressioneRegolare(debug_on=debug_on, debug_path=debug_path)
        Log.new("\tTempo di calcolo della diagnosi con espressioneRegolare",
                f"{Log.cronometro()}s")
        Log.new("\tOsservazione Lineare", f"{osservazioneLineare}")
        Log.new("\tDiagnosi Lineare", f"{diagnosi}")

        # Genera file in output
        Main.outputSerializer("compito3", rete=None, sc=scol, output_path=output_path, osservazioneLineare=osservazioneLineare)

        return diagnosi

    @staticmethod
    def compito4(spazio: SpazioComportamentale, output_path: str) -> Diagnosticatore:
        """
        Genera il diagnosticatore a partire dallo SpazioComportamentale (come generato da compito1).
        Inoltre salva su disco il file di output corrispondente nella posizione specificata in output_path (o in
        alternativa nella stessa cartella dell'input).

        :param spazio: lo SpazioComportamentale generato da Compito 1
        :param output_path: il percorso su disco dove salvare il file XML che descrive l'output di Compito 4
        :return: il Diagnosticatore corrispondente
        """
        Log.logtime()
        Log.new("Compito 4 - Generazione del Diagnosticatore per lo spazio comportamentale in ingresso","")

        Log.cronometro()
        diagnosticatore = spazio.generaDiagnosticatore()
        Log.new("\tTempo di generazione del Diagnosticatore",
                f"{Log.cronometro()}s")
        diagnosticatore.logStats()

        # Genera file in output
        Main.outputSerializer("compito4", rete=None, sc=diagnosticatore, output_path=output_path)

        return diagnosticatore

    @staticmethod
    def compito5(diag: Diagnosticatore, osservazioneLineare: List[str], output_path: str) -> str:
        """
        Genera la diagnosi relativa all'osservazione lineare a partire dal Diagnosticatore (come generato da compito 4)
        e ad una osservazione lineare.
        Inoltre salva su disco il file di output corrispondente nella posizione specificata in output_path (o in
        alternativa nella stessa cartella dell'input).

        :param diag: il Diagnosticatore di una ReteFA
        :param osservazioneLineare: una lista ordinata di stringhe dove ogni stringa rappresenta un'osservazione su reteFA
        :param output_path: il percorso su disco dove salvare il file XML che descrive l'output di Compito 4
        :return: la stringa di diagnosi relativa all'osservazione lineare data sulla ReteFA
        """
        Log.logtime()
        Log.new("Compito 5 - Calcolo della diagnosi, a partire dal diagnosticatore per la rete", "")

        Log.cronometro()
        diagnosi = diag.diagnosiLineare(osservazioneLineare)
        Log.new("\tTempo di calcolo della diagnosi con espressioniRegolari",
                f"{Log.cronometro()}s")
        Log.new("\tOsservazione Lineare", f"{osservazioneLineare}")
        Log.new("\tDiagnosi Lineare", f"{diagnosi}")
        # Genera file in output
        Main.outputSerializer("compito5", rete=None, sc=None, output_path=output_path, osservazioneLineare=osservazioneLineare)

        return diagnosi

    def fromCompito2(xmlPath: str):
        """
        Estrazione delle informazioni necessarie al compito 3 a partire dall'output del compito 2:
        estrae lo spazio comportamentale e la reteFA dall' XML in uscita al compito 2.
        :param xmlPath: xml che descrive lo spazio comportamentale relativo ad un osservazione lineare
        :return: lo spazio comportamentale relativo all'osservazione lineare, la reteFA e l'osservazione lineare
        """
        reteFA = ReteFA('')
        scol = SpazioComportamentale()
        ol = None
        xsdPath = 'inputs/output_compito2.xsd'
        schema = xmlschema.XMLSchema(xsdPath)
        if schema.is_valid(xmlPath):
            tree = ET.parse(source=xmlPath)
            root = tree.getroot()

            # todo: potrebbe essere necessario fare un parsing a List[str] di ol
            ol = root.find('osservazioneLineare').replace("'", "").strip("][").split(", ")

            pickledb64 = root.find('base64').text

            (reteFA, scol) = loads(b64decode(pickledb64))

        return reteFA, scol, ol

    def fromCompito1(xmlPath: str):
        """
        Estrazione delle informazioni necessarie al compito 4 a partire dall'output del compito 1:
        estrae lo spazio comportamentale e la reteFA dall' XML in uscita al compito 1.
        :param xmlPath: xml che descrive lo spazio comportamentale
        :return: lo spazio comportamentale e la reteFA costruiti a partire dall'XML
        """
        sc = SpazioComportamentale()
        reteFA = ReteFA('')
        xsdPath = 'inputs/output_compito1.xsd'
        schema = xmlschema.XMLSchema(xsdPath)
        if schema.is_valid(xmlPath):
            tree = ET.parse(source=xmlPath)
            root = tree.getroot()

            (reteFA, sc) = loads(b64decode(root.find('base64').text))

        return reteFA, sc

    def fromCompito4(xmlPath: str):
        """
        Estrazione delle informazioni necessarie al compito 5 a partire dall'output del compito 4:
        estrae il diagnosticatore dall' XML in uscita al compito 4.
        :param xmlPath: xml che descrive lo spazio comportamentale relativo ad un osservazione lineare
        :return: il diagnosticatore costruito a partire dall'XML
        """
        diag = Diagnosticatore()
        xsdPath = 'inputs/output_compito4.xsd'
        schema = xmlschema.XMLSchema(xsdPath)
        if schema.is_valid(xmlPath):
            tree = ET.parse(source=xmlPath)
            root = tree.getroot()

            (reteFA, diag) = loads(b64decode(root.find('base64').text))

        return reteFA, diag

#################
## RUN TARGETS ##
#################

if __name__ == '__main1__':
    # todo: fai in modo che la description sia leggibile dall'utente
    parser = argparse.ArgumentParser(description=
"""retefa -
 Calcola la diagnosi di rilevanza di una rete di automi a stati finiti (ReteFA),
 a fronte di una particolare osservazione lineare effettuata sui comportamenti.
 
 Una ReteFA è descritta da un file XML. Si faccia riferimento agli esempi nella cartella inputs.
 
 Un'osservazione lineare è una lista di osservazioni sulla rete.
    Esempio: [\"o1\", \"o2\"]
 
 Una diagnosi di rilevanza è un'espressione regolare ove sono presenti i seguenti operatori:
    - Concatenazione: ab
    - Alternativa:    a|b
    - Ripetizione:    a*
    - Raggruppamento: (ab)c
    
 Questa applicazione è in grado di eseguire i seguenti compiti
    1- Generazione di uno Spazio Comportamentale da una reteFA
        Richiede in ingresso
            - una reteFA descritta da un file XML
        
    2- Generazione di uno Spazio Comportamentale relativo a un'Osservazione Lineare da una ReteFA e una OL
        Richiede in ingresso
            - una reteFA descritta da un file XML o dall'output di Compito 1
            - una Osservazione Lineare 
            
    3- Calcolo di una Diagnosi Lineare a partire da uno Spazio Comportamentale relativo a un'Osservazione Lineare
        Richiede in ingresso
            - uno  Spazio Comportamentale relativo a un'Osservazione Lineare, ovvero l'output di Compito 2
            
    4- Generazione di un Diagnosticatore a partire da uno Spazio Comportamentale
        Richiede in ingresso
            - uno Spazio Comportamentale, ovvero l'output di Compito 1
            
    5- Calcolo di una Diagnosi Lineare a partire da un Diagnosticatore e un'Osservazione Lineare
        Richiede in ingresso
            - un Diagnosticatore, ovvero l'output di Compito 4
    
 I compiti devono essere dunque svolti in uno dei seguenti ordini. Gli output di un compito possono essere usati come
 input del successivo nella catena di esecuzione:
    A- Compito 1 -> Compito 4 -> Compito 5 
       la diagnosi è calcolata con Espressioni Regolari, ovvero il Diagnosticatore.
       Utile se si pensa di riusare il diagnosticatore per più diagnosi relative ad Osservazioni Lineari diverse sulla 
       stessa rete
      
    B- (Compito 1 -> )Compito 2 -> Compito 3
       la diagnosi è calcolata con Espressione Regolare, sulla chiusura lineare. Si può risparmia il tempo di parsing e
       conversione della ReteFA dall'XML alla struttura dati interna usando come input l'output di Compito 1.
       Utile per reti grandi dove è molto oneroso calcolare il diagnosticatore.
       
 È possibile interrompere l'esecuzione del programma in ogni momento premendo su Ctrl-C.
       
    """)
    parser.add_argument("-c", "--compito", type=int, help="Numero del compito da eseguire", choices=[1, 2, 3, 4, 5])
    parser.add_argument("-r", "--reteFA", help="File di input XML contenente la Rete FA")
    parser.add_argument("-o", "--ol", help="Osservazione Lineare, scritta tra quadre, es. [\"o1\", \"o2\"]")
    parser.add_argument("-O", "--outputpath", help="Path della cartella di output desiderata", default=Main.DEFAULT_OUTPUT_PATH)
    # todo: check su -p e -f, non è chiara la differenza
    parser.add_argument("-d", "--debugInfo", action='store_true', default=False,
                        help="Genera ulteriori info di debug (fra cui i grafi delle iter di espressioneRegolare in Compito 3)")
    parser.add_argument("-p", "--precedente", action='store_true', default=False, help="Utilizza output di un compito precedente")
    parser.add_argument("-f", "--fileOutput", help="path di un file di input contenente l'output prodotto da un compito precedente")

    args = parser.parse_args()
    print(f"Esecuzione del compito {args.compito} sull'input '{args.reteFA}'.\nPath dell'output: '{args.outputPath}'")
    t = time.time()

    # Log iniziale
    Log.logtime("Inizio esecuzione")
    Log.new("Compito", args.compito)
    Log.new("File input", args.reteFA)
    Log.new("Path input", args.outputPath)

    # Logica di gestione degli input
    if args.compito == 1:
        # controllo validità input
        if args.reteFA is not None:
            s1, r1 = Main.compito1(args.reteFA, args.outputPath)
        else:
            print('Rete FA non inserita')
    elif args.compito == 2:
        # controllo validità input
        if args.reteFA is not None:
            if args.ol is not None:
                ol = args.ol.strip(']["').split(',')
                r2a, scol = Main.compito2(args.reteFA, ol, args.outputPath)
            else:
                print('Osservazione Lineare non inserita')
        else:
            print('rete FA non inserita')
    elif args.compito == 3:
        # controllo validità input
        if not args.precedente:
            if args.reteFA is not None:
                if args.ol is not None:
                    ol = args.ol.strip(']["').split(',')
                    r2a, scol = Main.compito2(args.reteFA, ol, args.outputPath)
                    d3 = Main.compito3(scol, args.outputPath, debug_on=args.debugInfo)
                    print(f"Diagnosi ottenuta da compito 3: {d3}")
                else:
                    print('Osservazione Lineare non inserita')
            else:
                print('rete FA non inserita')
        elif args.precedente:
            if args.fileOutput is not None:
                reteFA, scol, ol = Main.fromCompito2(args.fileOutput)
                d3 = Main.compito3(scol, ol, args.outputPath, debug_on=args.debugInfo)
                print(f"Diagnosi ottenuta da compito 3: {d3}")
            else:
                print('percorso file non inserito')
        else:
            print('parametri non validi')
    elif args.compito == 4:
        # controllo validità input
        if not args.precedente:
            if args.reteFA is not None:
                reteFA, sc = Main.compito1(args.reteFA, args.outputPath)
                diagnosticatore4 = Main.compito4(sc, args.outputPath)
            else:
                print('rete FA non inserita')
        elif args.precedente:
            if args.fileOutput is not None:
                reteFA, sc = Main.fromCompito1(args.fileOutput)
                diagnosticatore4 = Main.compito4(sc, args.outputPath)
            else:
                print('percorso file non inserito')
        else:
            print('parametri non validi')
    elif args.compito == 5:
        # controllo validità input
        if not args.precedente:
            if args.reteFA is not None:
                if args.ol is not None:
                    ol = args.ol.strip(']["').split(',')
                    r1, s1 = Main.compito1(args.reteFA, args.outputPath)
                    diagnosticatore4 = Main.compito4(s1, args.outputPath)
                    d5 = Main.compito5(diagnosticatore4, ol, args.outputPath)
                    print(f"Diagnosi ottenuta da Diagnosticatore: {d5}")
            else:
                print('Rete FA non inserita!')
        elif args.precedente:
            if args.fileOutput is not None:
                    if args.ol is not None:
                        ol = args.ol.strip(']["').split(',')
                        reteFA, diag = Main.fromCompito4(args.fileOutput)
                        d5 = Main.compito5(diag, ol, "")
                        print(f"Diagnosi ottenuta da Diagnosticatore: {d5}")
                    else:
                        print('Osservazione Lineare non inserita')
            else:
                print('Percorso file non inserito')
        else:
            print('Parametri in input non validi')

    elapsed = time.time() - t
    print(f"Tempo di esecuzione: {elapsed}")

# Target di esecuzione per il test dell'output di tutti i compiti
if __name__ == '__main__':
    # xmlPath = 'inputs/input.xml'
    # ol = ["o3", "o2"]
    # ol = ["o3", "o2", "o3", "o2"]
    # ol = ["o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2","o3","o2"]
    # ol = ["o1","o2","o1"]

    # xmlPath = 'inputs/input_rete2.xml'
    # ol = ["act", "sby", "nop"]

    xmlPath = 'inputs/input_rete3.xml'
    ol = ["o1"]

    # xmlPath = 'inputs/input_reteCane.xml'
    # ol = ["Calmo", "Abbaia"]

    # Test Output Compito 1
    r1, s1 = Main.compito1(xmlPath, Main.DEFAULT_OUTPUT_PATH)
    # Main.outputSerializer("compito1", r1, s1, output_path="outputs/")

    # Test Output Compito 2
    scol = None
    # try:
    r2a, scol2a = Main.compito2(xmlPath, ol, Main.DEFAULT_OUTPUT_PATH)
    # r2b, scol2b = Main.compito2(r1, ol, Main.DEFAULT_OUTPUT_PATH)
    # scol = scol2a if scol2a else scol2b if scol2b else None

    scol = scol2a

    # Test Output Compito 3
    d3 = Main.compito3(scol, ol, Main.DEFAULT_OUTPUT_PATH, debug_on=True)

    # Test Output Compito 4
    diagnosticatore4 = Main.compito4(s1, Main.DEFAULT_OUTPUT_PATH)

    # Test Output Compito 5
    d5 = Main.compito5(diagnosticatore4, ol, Main.DEFAULT_OUTPUT_PATH)

    # Stampo le diagnosi
    print(f"Diagnosi ottenute:\nDa compito 3: {d3}\nDa compito 5: {d5}")


if __name__ == '__compito 5__':
    # ol = ["o3", "o2", "o3", "o2"]
    ol = ["o3", "o2"]
    # Test compito 5
    xmlPath = 'inputs/input.xml'
    rete = ReteFA.fromXML(xmlPath)

    sc = SpazioComportamentale()
    sc.creaSpazioComportamentale(rete)
    sc.potaturaRidenominazione()

    diagnosticatore = sc.generaDiagnosticatore()

    diagnosi = diagnosticatore.diagnosiLineare(ol)

    print(f"Diagnosi lineare per ol {ol}: {diagnosi}")

if __name__ == '__compito 4__':

    # Test compito 4
    xmlPath = 'inputs/input.xml'
    rete = ReteFA.fromXML(xmlPath)

    sc = SpazioComportamentale()
    sc.creaSpazioComportamentale(rete)
    sc.potaturaRidenominazione()

    diagnosticatore = sc.generaDiagnosticatore()

    print(f"fine")

if __name__ == '__compito3__':
    # Test compito 3
    xmlPath = 'inputs/input.xml'
    rete = ReteFA.fromXML(xmlPath)
    ol = ["o3", "o2"]

    scol = SpazioComportamentale()
    scol.creaSpazioComportamentaleOsservazioneLineare(rete, ol)
    scol.potaturaRidenominazione()

    regexp = scol.espressioneRegolare()

    print(f"Risultato: {regexp}")

if __name__ == '__test1__':
    xmlPath = 'inputs/input.xml'

    out = ReteFA.validateXML(xmlPath)
    print(out)

if __name__ == '__test2__':
    """Test per l'inizializzazione di una rete a partire da un input"""
    xmlPath = 'inputs/input.xml'

    rete = ReteFA.fromXML(xmlPath)

    # Caso test: spazio comportamentale vuoto
    # ol = []
    # Caso test: potatura totale
    # ol = ["o3",""]
    # Caso test: etichette non presenti nella ReteFA
    # ol = ["o9803","o45"]
    # Caso test: osservazione valida
    ol = ["o3", "o2"]

    # Test validaOsservazioneLineare
    # print(rete.verificaOsservazioneLineare([]))
    print(rete.verificaOsservazioneLineare(ol))
    # print(rete.verificaOsservazioneLineare(["o3", "o4"]))
    # print(rete.verificaOsservazioneLineare(["o3", "o2", "o4"]))
    # print(rete.verificaOsservazioneLineare(["o5", "o2", "o4"]))

    sc = SpazioComportamentale()
    sc.creaSpazioComportamentale(rete)
    sc.potaturaRidenominazione()

    scol = SpazioComportamentale()
    scol.creaSpazioComportamentaleOsservazioneLineare(rete, ol)
    scol.potaturaRidenominazione()
