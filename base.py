#!/usr/bin/python3
import os
import sys
sys.path.append(os.path.abspath("{}/LIBAPGpy/LIBAPGpy".format(os.environ["APG_PATH"])))
import libapg as apg
from time import sleep
import asyncio
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
import json
from datetime import datetime

class BASMessage(apg.msg.Message):
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
    
            
 
class BASApp(apg.Application):
    def __init__(self):
        default_options_values={"appname":"BAS","whatwho":True,"bas-sale-period":"10", "bas-price":"1"}
        super().__init__(default_options_values)
        self.mandatory_parameters += [] # No mandatory parameter for this app
        
        self.appname = self.params["appname"]
        self.period = float(self.params["bas-sale-period"])
        self.price = float(self.params["bas-price"])
        self.sending_in_progress = None

        self.id = int(self.params['id'])
        self.total = int(self.params['total'])
        
        # init variable
        self.ca_global = 0
        self.ca_local = 0
        self.tmp_local = 0
        self.request_sc = False

        self.v_clock = [0]*int(self.total)
        self.hist = []
        self._push_history()
        self.snapshot_started = False

        
        if self.check_mandatory_parameters():
            self.config_gui()
            self.end_initialisation()

    def start(self):
        super().start()
        self.remove_footer_gui()
        self.update_v_clock_gui()

    def receive(self, pld, src, dst, where):
        if self.started  and self.check_mandatory_parameters():
            self.vrb("{}.rcv(pld={}, src={}, dst={}, where={})".format(self.APP(),pld, src, dst, where), 6)
            super().receive(pld, src=src, dst=dst, where=where)
            received_message=BASMessage(pld,self)

            # Vérification que le msq lui est destiné
            if self.appname != dst:
                return
            
            # Log dans le terminal
            #self.vrb("{}.rcv(pld={}, src={}, dst={}, where={})".format(self.APP(),pld, src, dst, where), 0)
            
            sleep(0.05)

            # Gestion de l'horloge vectorielle
            v_clock_msg = received_message.content["v_clock"] if "v_clock" in received_message.content else None

            self._update_clock(v_clock_msg)
            
            if received_message.payload() == "debutSC":
                # Entrée en SC
                self.ca_global += self.tmp_local
                self.tmp_local = 0
                # Fin de SC
                self._push_history()

                payload = "finSC"
                text = "ca_global~" + str(self.ca_global) + "^v_clock~" + json.dumps(self.v_clock)
                message = BASMessage(text, self, payload)
                self.snd(str(message), who="NET")
                self.request_sc = False

                #self.vrb("BAS envoie vers NET : {})".format(message),0)

                # Mise à jour interface graphique
                self.update_gui()
                return

            if received_message.payload() == "newCA":
                self.ca_global = float(received_message.content["ca_global"])
                self.update_gui()
                return

            if received_message.payload() == "finSnapshot":
                etatGeneral = received_message.content['etatGeneral']
                prepostMsg = received_message.content['prepostMsg']

                self.vrb("etatGeneral: " + etatGeneral, 0)
                self.vrb("prepostMsg: " + prepostMsg, 0)

                self.snapshot_started = False

                try:
                    if not os.path.exists("backup"):
                        os.makedirs('backup')
                    with open(f"backup/backup_{datetime.now()}", "a") as backup_file:
                        backup_file.write(f"{received_message.content['etatGeneral']} \n")
                        backup_file.write(f"{received_message.content['prepostMsg']} \n")
                except Exception as e:
                    self.vrb(f"Log Error: {e}", 0)

                return
            
            if received_message.payload() == "demandeEtatLocal":
                payload = "etatLocal"
                text = "bilan~" + received_message.content["bilan"] + "^v_clock~" + json.dumps(self.hist[-1][0]) + "^etat_local~" + json.dumps(self.hist[-1][1])
                message = BASMessage(text, self, payload)
                self.snd(str(message), who="NET")
                return


        else:
            self.vrb_dispwarning("Application {} not started".format(self.APP()))

    def _push_history(self):
        self.hist.append((
            self.v_clock,
            {
                "ca_global": self.ca_global,
                "tmp_local": self.tmp_local,
                "ca_local": self.ca_local
            }
        ))
    
    def _update_clock(self, v_clock=None):
        if v_clock:
            v_clock = json.loads(v_clock)
            for i in range(len(v_clock)):
                self.v_clock[i] = max(int(v_clock[i]), self.v_clock[i])
        self.v_clock[self.id] += 1
        self.update_v_clock_gui()

    def snapshot_button_action(self):
        if not self.snapshot_started:
            self.snapshot_started = True
            payload = "debutSnapshot"
            etatLocal = {
                "ca_global": self.ca_global,
                "ca_local": self.ca_local,
                "tmp_local": self.tmp_local
            }
            text = "etatLocal~" + json.dumps(etatLocal) + "^v_clock~" + json.dumps(self.v_clock)
            message = BASMessage(text, self, payload)
            self.snd(str(message), who="NET")
    
    def sale_button_action(self, graphic_price=None):
        """ When sale button on app area is pushed """
        self.vrb("sale_button_action(graphic_msg={})".format(graphic_price),6)

        self._update_clock()
        
        if graphic_price != None:
            self.ca_local += float(graphic_price.get())
            self.tmp_local += float(graphic_price.get())
        else:
            self.ca_local += self.price
            self.tmp_local += self.price

        if self.request_sc == False:
            payload = "demandeSC"
            message = BASMessage("",self, payload)
            self.snd(str(message), who="NET")
            self.request_sc = True
            #self.vrb("BAS envoie vers NET : {})".format(message),0)

        # Mise à jour interface graphique
        self.update_gui()

    def start_auto_sale_button_action(self, graphic_price=None, graphic_period=None):
        """ When sale button on app area is pushed """
        self.vrb("start_auto_sale_button_action(graphic_price={}, graphic_period={})".format(graphic_price, graphic_period),6)

        if self.sending_in_progress:
            self.vrb("Already sending, reseting parameters",3)
            self.sending_in_progress.cancel()
            self.sending_in_progress = None

        self.sale_button_action(graphic_price)

        if graphic_period != None:
            self.period = float(graphic_period.get())
        
        self.sending_in_progress = self.loop.call_later(float(self.period), self.start_auto_sale_button_action, graphic_price, graphic_period)
        self.gui.tk_instr('self.sale_auto_btn.config(text="Running...")')

    def stop_auto_sale_button_action(self):
        """ When send button on app area is pushed """
        if self.sending_in_progress:
            self.sending_in_progress.cancel()
            self.sending_in_progress = None
        else:
            self.vrb_dispwarning("No sending in progress")
            return
        self.gui.tk_instr('self.sale_auto_btn.config(text="Vendre Auto")')

    def update_gui(self):
        self.gui.tk_instr("""
self.ca_global_value.set({})
self.ca_local_value.set({})
self.tmp_local_value.set({})
self.request_sc_value.set({})
""".format(self.ca_global, self.ca_local, self.tmp_local, self.request_sc))

    def update_v_clock_gui(self):
        self.gui.tk_instr("""
v_clock = {}
v = "["
for clock in v_clock:
    v+= " " + str(clock) + ","
v = v[:-1]
v+=" ]"
self.v_clock_string_var.set(v)
""".format(self.v_clock))

    def remove_footer_gui(self):
        self.gui.tk_instr("""
self.send_zone.pack_forget()
self.subscribe_zone.pack_forget()
""")

    def config_gui(self):
        """ GUI settings """
        self.gui.tk_instr("""
self.app_zone = tk.LabelFrame(self.root, text="{}")

self.line1 = tk.Frame(self.app_zone)

self.price_string_var = tk.StringVar()
self.price_string_var.set({})
self.price_entry = tk.Entry(self.line1, width=6, textvariable = self.price_string_var, justify="right")
self.price_entry.pack(side="left")
self.sale_btn = tk.Button(self.line1, text="Vendre", command=partial(self.app().sale_button_action,self.price_string_var), activebackground="red", foreground="red", width=10)
self.sale_btn.pack(side="left", padx=4)

self.time_string_var = tk.StringVar()
self.time_string_var.set("1")
self.time_entry = tk.Entry(self.line1, width=6, textvariable = self.time_string_var, justify="right")
self.time_entry.pack(side="left", padx=(80,0))
self.sale_auto_btn = tk.Button(self.line1, text="Vendre Auto", command=partial(self.app().start_auto_sale_button_action,self.price_string_var,self.time_string_var), activebackground="red", foreground="red", width=15)
self.sale_auto_btn.pack(side="left", padx=4)
self.stop_sale_auto_btn = tk.Button(self.line1, text="Stop Vendre", command=partial(self.app().stop_auto_sale_button_action), activebackground="red", foreground="red", width=15)
self.stop_sale_auto_btn.pack(side="left", padx=2)

self.line2 = tk.Frame(self.app_zone)

self.ca_global_lab = tk.Label(self.line2, text="ca_global: ")
self.ca_global_lab.pack(side="left")
self.ca_global_value = tk.IntVar()
self.ca_global_value.set({})
tk.Label(self.line2, textvariable=self.ca_global_value).pack(side="left", padx=2)
self.ca_local_lab = tk.Label(self.line2, text="ca_local: ", justify="right")
self.ca_local_lab.pack(side="left", padx=(80,0))
self.ca_local_value = tk.IntVar()
self.ca_local_value.set({})
tk.Label(self.line2, textvariable=self.ca_local_value).pack(side="left", padx=2)
self.tmp_local_lab = tk.Label(self.line2, text="tmp_local: ")
self.tmp_local_lab.pack(side="left", padx=(80,0))
self.tmp_local_value = tk.IntVar()
self.tmp_local_value.set({})
tk.Label(self.line2, textvariable=self.tmp_local_value).pack(side="left", padx=2)
self.request_sc_lab = tk.Label(self.line2, text="request_sc: ")
self.request_sc_lab.pack(side="left", padx=(80,0))
self.request_sc_value = tk.IntVar()
self.request_sc_value.set({})
tk.Label(self.line2, textvariable=self.request_sc_value).pack(side="left", padx=2)

self.line3 = tk.Frame(self.app_zone)

tk.Label(self.line3, text="v_clock : ").pack(side="left", padx=2)
self.v_clock_string_var = tk.StringVar()
self.v_clock_string_var.set("[]")
tk.Label(self.line3, textvariable=self.v_clock_string_var).pack(side="left", padx=2)
self.snapshot_btn = tk.Button(self.line3, text="Snapshot", command=partial(self.app().snapshot_button_action), activebackground="red", foreground="red", width=10)
self.snapshot_btn.pack(side="right", padx=4)

self.line1.pack(side="top", fill=tk.BOTH, expand=1, pady=5)
self.line2.pack(side="top", fill=tk.BOTH, expand=1, pady=10)
self.line3.pack(side="top", fill=tk.BOTH, expand=1, pady=20)
self.app_zone.pack(fill="both", expand="yes", side="top", pady=5)
""".format(self.APP(), self.price, self.ca_global, self.ca_local, self.tmp_local, self.request_sc)) # Graphic interface (interpreted if no option notk)

    
app = BASApp()
if app.params["auto"]:
    app.start()
else:
    app.dispwarning("app not started")

