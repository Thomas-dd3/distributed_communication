#!/usr/bin/python3
import os
import sys
sys.path.append(os.path.abspath("{}/LIBAPGpy/LIBAPGpy".format(os.environ["APG_PATH"])))
import libapg as apg
from time import sleep
import asyncio
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
import json

class NETMessage(apg.msg.Message):
    """Application-specific message treatment"""
    def __init__(self, text, app, payload=None):
        super().__init__(text, app)
        
        self.fields += ["payload"]
        if payload != None:
            self.content["payload"] = payload

        if len(text) > 0:
            self.parse_text(text)

    def payload(self):
        return self.content["payload"]
    


 
class NETApp(apg.Application):
    def __init__(self):

        default_options_values={"appname":"NET", "whatwho":True}
        super().__init__(default_options_values)
        self.mandatory_parameters += [] # No mandatory parameter for this app
        self.appname = self.params["appname"]

        self.id = int(self.params['id'])
        self.total = int(self.params['total'])

        # initialisation algorithme de la file d'attente partagée (horloge logique/estampille)
        self.clock = 0
        self.tab = [("lib", 0, 0)] * self.total
        self.debutSC_sent = False

        # initialisation algorithme du snapshot
        self.snapshoted = False
        self.initiateur = False
        self.bilan = 0
        self.etatGeneral = [None] * self.total
        self.prepostMsg = []
        self.nbMsgAttendus = 0
        self.snapHeader = None
        
        self.etatLast = [0] * self.total
        self.prepostLast = [0] * self.total

        if self.check_mandatory_parameters():
            self.config_gui()
            self.end_initialisation()
            self.gui.tk_instr("""
self.send_zone.pack_forget()
self.subscribe_zone.pack_forget()
""")

    def start(self):
        super().start()
        self.remove_footer_gui()

    def receive(self, pld, src, dst, where):
        """When a message is received """
        if self.started  and self.check_mandatory_parameters():
            self.vrb("{}.rcv(pld={}, src={}, dst={}, where={})".format(self.APP(),pld, src, dst, where), 6)
            super().receive(pld, src=src, dst=dst, where=where) # Useful for logs management, mostly
            received_message=NETMessage(pld,self)
            
            # Vérification que le msg lui est destiné
            if self.appname != dst:
                return
            
            #self.vrb("{}.rcv(pld={}, src={}, dst={}, where={})".format(self.APP(),pld, src, dst, where), 0)

            sleep(0.2)

            # Utilisé pour concaténer le "snapshoted~false/true"
            text = ""


            typeMsg = received_message.content["type"] if "type" in received_message.content  else None
            s_id = int(received_message.content["s_id"]) if "s_id" in received_message.content  else None
            s_clock = int(received_message.content["s_clock"]) if "s_clock" in received_message.content  else None
            requester_id = int(received_message.content["requester_id"]) if "requester_id" in received_message.content  else None
            ca_global = float(received_message.content["ca_global"]) if "ca_global" in received_message.content  else None

            snapHeader = json.loads(received_message.content["snapHeader"]) if "snapHeader" in received_message.content  else False

            #################### Algorithme du snapshot #####################################################
            
            ### Réception de msg provenant de base ###

            # reception d'un début de snapshot dans le Controller de Base
            if received_message.payload() == "debutSnapshot":
                v_clock = json.loads(received_message.content["v_clock"])
                etatLocal = json.loads(received_message.content["etatLocal"])

                self.clock += 1
                self.snapshoted = True
                self.initiateur = True
                self.nbMsgAttendus = self.bilan
                self.etatGeneral[self.id] = (v_clock, etatLocal)

                self.snapHeader = {
                    "snapshoted": True,
                    "snap_v_clock": v_clock,
                    "snap_initiateur": self.id
                }
                
                self.update_gui()
                return
            

            if received_message.payload() == "etatLocal":
                self.clock += 1

                bilan = received_message.content["bilan"]
                v_clock = received_message.content["v_clock"]
                etat_local = received_message.content["etat_local"]

                payload = "etat"
                text = "snapHeader~" + json.dumps(self.snapHeader) + "^bilan~" + bilan + "^v_clock~" + v_clock + "^etat_local~" + etat_local + "^s_clock~" + str(self.clock) + "^s_id~" + str(self.id)
                message = NETMessage(text, self, payload)
                self.snd(str(message), who="NET")

                self.update_gui()
                return


            ### Réception de msg provenant de controller ###
                

            if snapHeader and (self.snapshoted == False):
                self.snapshoted = True
                # TODO check bilan = received_message.content["bilan"]

                payload = "demandeEtatLocal"
                text = "snapHeader~" + json.dumps(snapHeader) + "^bilan~" + str(self.bilan)
                message = NETMessage(text, self, payload)
                self.snd(str(message), who="BAS")


            if received_message.payload() == "etat":
                # check si msg déjà reçu
                if self.etatLast[s_id] >= s_clock:
                    return

                if self.initiateur == True:
                    etat_local = json.loads(received_message.content["etat_local"])
                    v_clock = json.loads(received_message.content["v_clock"])
                    self.etatGeneral[s_id] = (v_clock, etat_local)

                    bilan = int(received_message.content["bilan"])
                    self.nbMsgAttendus += bilan


                    if ( self.getUsedSizeTab(self.etatGeneral) == self.total) and (self.nbMsgAttendus == 0):
                        # Fin algo, envoyer un msg à Base
                        payload = "finSnapshot"
                        text = "etatGeneral~" + json.dumps(self.etatGeneral) + "^prepostMsg~" + json.dumps(self.prepostMsg)
                        message = NETMessage(text, self, payload)
                        self.snd(str(message), who="BAS")
                else:
                    # forward msg
                    self.etatLast[s_id] = s_clock
                    self.snd(pld, who="NET")
                
                self.update_gui()
                return

            if received_message.payload() == "prepost":
                # check si msg déjà reçu
                if self.prepostLast[s_id] >= s_clock:
                    return

                if self.initiateur == True:
                    prepostMessage = received_message.content["prepostMessage"]
                    
                    self.nbMsgAttendus -= 1
                    self.prepostMsg.append(prepostMessage)

                    if (self.getUsedSizeTab(self.etatGeneral) == self.total) and (self.nbMsgAttendus == 0):
                        # Fin algo, envoyer un msg à Base
                        payload = "finSnapshot"
                        text = "etatGeneral~" + json.dumps(self.etatGeneral) + "^prepostMsg~" + json.dumps(self.prepostMsg)
                        message = NETMessage(text, self, payload)
                        self.snd(str(message), who="BAS")
                else:
                    # forward msg
                    self.prepostLast[s_id] = s_clock
                    self.snd(pld, who="NET")
                
                self.update_gui()
                return



            ##################### Message reçu de Base #####################################################

            if received_message.payload() == "demandeSC":
                self.clock += 1
                self.tab[self.id] = ("req", self.clock, self.clock)

                payload = "requete"
                text = "type~req^s_clock~" + str(self.clock) + "^s_id~" + str(self.id)
                message = NETMessage(text, self, payload)
                self.snd(str(message), who="NET")
                self.update_gui()
                return

            if received_message.payload() == "finSC":
                self.clock += 1
                self.tab[self.id] = ("lib", self.clock, self.clock)
                self.debutSC_sent = False

                ### Partie algo snapshot
                text = ""
                self.bilan += (self.total - 1)
                text += "snapHeader~" + json.dumps(self.snapHeader) + "^v_clock~" + received_message.content["v_clock"] + "^"
                ###

                payload = "liberation"
                text += "type~lib^s_clock~" + str(self.clock) + "^s_id~" + str(self.id) + "^ca_global~" + received_message.content["ca_global"]
                message = NETMessage(text, self, payload)
                self.snd(str(message), who="NET")
                self.update_gui()
                return



            ##################### Algorithme de la file d'attente répartie #################################

            # On vérifie si on a déjà eu ce message grâce à l'horloge lorgique
            self.vrb("{}.rcv(pld={}, src={}, dst={}, where={})".format(self.APP(),pld, src, dst, where), 0)
            self.vrb("ns_id: " + str(s_id), 0)
            if self.tab[s_id][2] >= s_clock:
                return

            # transmission du message aux autres NET si besoin
            if (not requester_id) or (requester_id and (self.id != requester_id)):
                # forward msg
                self.snd(pld, who="NET")

            if received_message.payload() == "requete":
                self.clock = max(self.clock, s_clock) + 1
                self.tab[s_id] = (typeMsg, s_clock, s_clock)

                payload = "accuse"
                text = "type~acc^s_clock~" + str(self.clock) + "^s_id~" + str(self.id) + "^requester_id~" + str(s_id)
                message = NETMessage(text, self, payload)
                self.snd(str(message), who="NET")
                

                self.check_start_sc()
                self.update_gui()
                return

            if received_message.payload() == "liberation":
                self.clock = max(self.clock, s_clock) + 1
                self.tab[s_id] = (typeMsg, s_clock, s_clock)

                v_clock = received_message.content["v_clock"]

                # Envoie du msg à BAS
                payload = "newCA"
                text = "ca_global~" + received_message.content["ca_global"] + "^v_clock~" + v_clock
                message = NETMessage(text, self, payload)
                self.snd(str(message), who="BAS")


                ### Partie Algo snapshot
                self.bilan -= 1

                if (snapHeader == False) and self.snapshoted:
                    self.clock += 1
                    payload = "prepost"

                    msg = {
                        "type": typeMsg,
                        "s_id": s_id,
                        "s_clock": s_clock,
                        "ca_global": ca_global,
                        "v_clock": v_clock
                    }

                    text = "prepostMessage~" + json.dumps(msg) + "^s_clock~" + str(self.clock) + "^s_id~" + str(self.clock)
                    message = NETMessage(text, self, payload)
                    self.snd(str(message), who="NET")

                self.check_start_sc()
                self.update_gui()
                return

            if received_message.payload() == "accuse":

                if self.id == requester_id:
                    self.clock = max(self.clock, s_clock) + 1
                    if self.tab[s_id][0] != "req":
                        self.tab[s_id] = ("acc", s_clock, s_clock)

                    self.check_start_sc()

                else:
                    self.tab[s_id] = (self.tab[s_id][0], self.tab[s_id][1], s_clock)
                
                self.update_gui()
                return

        else:
            self.vrb_dispwarning("Application {} not started".format(self.APP()))
    
    
    def getUsedSizeTab(self, tab):
        nb = 0
        for value in tab:
            if value != None:
                nb += 1
        return nb
    
    def check_start_sc(self):
        if self.debutSC_sent:
            return

        if self.tab[self.id][0] == "req":
            my_turn = True
            for i in range(self.total):
                if self.id == i:
                    continue
                if (int(self.tab[self.id][1]) > int(self.tab[i][1])) or \
                    (int(self.tab[self.id][1]) == int(self.tab[i][1]) and int(self.id) > int(i)):
                    my_turn = False
                    self.vrb("my_turn false - i: {}".format(i),1)

            if my_turn:
                payload = "debutSC"
                message = NETMessage("", self, payload)
                self.snd(str(message), who="BAS")
                self.debutSC_sent = True


    def update_gui(self):
        self.gui.tk_instr("""
self.clock_value.set({})
tab = {}
for i in range(len(tab)):
    t, tc, lc = self.tab_gui[i]
    t.set(tab[i][0])
    tc.set(tab[i][1])
    lc.set(tab[i][2])

self.snapshoted_string_var.set({})
self.initiateur_string_var.set({})
self.bilan_int_var.set({})
self.nbMsgAttendus_string_var.set({})
""".format(self.clock, self.tab, self.snapshoted, self.initiateur, self.bilan, self.nbMsgAttendus))

    def remove_footer_gui(self):
        self.gui.tk_instr("""
self.send_zone.pack_forget()
self.subscribe_zone.pack_forget()
""")
    
    def config_gui(self):
        ## Interface
        self.gui.tk_instr("""
self.app_zone = tk.LabelFrame(self.root, text="{}")

self.line1 = tk.Frame(self.app_zone)
self.id_lab = tk.Label(self.line1, text="id: ")
self.id_lab.pack(side="left")
self.id_value = tk.IntVar()
self.id_value.set({})
tk.Label(self.line1, textvariable=self.id_value).pack(side="left", padx=2)
self.clock_lab = tk.Label(self.line1, text="clock: ")
self.clock_lab.pack(side="left", padx=(100,0))
self.clock_value = tk.IntVar()
self.clock_value.set({})
tk.Label(self.line1, textvariable=self.clock_value).pack(side="left", padx=2)
tk.Label(self.line1, text="", width=50).pack(side="left", padx=2) # To enlarge the size of the windows

self.line2 = tk.Frame(self.app_zone)

tab = {}
self.tab_gui = [None]*len(tab)
for i in range(len(tab)):
    t = tk.StringVar()
    t.set(tab[i][0])
    tc = tk.IntVar()
    tc.set(tab[i][1])
    lc = tk.IntVar()
    lc.set(tab[i][2])

    tk.Label(self.line2, text=i, width=10, justify="center").grid(row=0, column=i)
    tk.Label(self.line2,textvariable=t).grid(row=1, column=i)
    tk.Label(self.line2,textvariable=tc).grid(row=2, column=i)
    tk.Label(self.line2,textvariable=lc).grid(row=3, column=i)
    self.tab_gui[i] = (t, tc, lc)

self.line3 = tk.Frame(self.app_zone)
tk.Label(self.line3, text="snapshoted: ").pack(side="left")
self.snapshoted_string_var = tk.StringVar()
self.snapshoted_string_var.set({})
tk.Label(self.line3, textvariable=self.snapshoted_string_var).pack(side="left", padx=2)
tk.Label(self.line3, text="initiate: ").pack(side="left", padx=4)
self.initiateur_string_var = tk.StringVar()
self.initiateur_string_var.set({})
tk.Label(self.line3, textvariable=self.initiateur_string_var).pack(side="left", padx=2)
tk.Label(self.line3, text="bilan: ").pack(side="left", padx=4)
self.bilan_int_var = tk.IntVar()
self.bilan_int_var.set({})
tk.Label(self.line3, textvariable=self.bilan_int_var).pack(side="left", padx=2)
tk.Label(self.line3, text="nbMsgAttendus: ").pack(side="left", padx=4)
self.nbMsgAttendus_string_var = tk.StringVar()
self.nbMsgAttendus_string_var.set({})
tk.Label(self.line3, textvariable=self.nbMsgAttendus_string_var).pack(side="left", padx=2)

self.line1.pack(side="top", fill=tk.BOTH, expand=1, pady=(10,5))
self.line2.pack(side="top", fill=tk.BOTH, expand=1, pady=10)
self.line3.pack(side="top", fill=tk.BOTH, expand=1, pady=20)
self.app_zone.pack(fill="both", expand="yes", side="top", pady=5)
""".format(self.APP(), self.id, self.clock, self.tab, self.snapshoted, self.initiateur, self.bilan, self.nbMsgAttendus)) # Graphic interface (interpreted if no option notk)

app = NETApp()
if app.params["auto"]:
    app.start()
else:
    app.dispwarning("app not started")

