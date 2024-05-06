from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.uix.textinput import TextInput
from kivy.uix.recycleview import RecycleView
from kivy.graphics import *
from kivy.uix.label import Label
from kivy.properties import ListProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.clock import Clock
from kivy.core.window import Window
from shared.client_message import constructMessage, MessageType, messageToJson

#************************************************************
#Custom classes (styled in layout.kv)

#scrollable message container
class Messages(RecycleView):
    def __init__(self, **kwargs):
        super(Messages, self).__init__(**kwargs)
        self.data = []

    def addMessage(self, sender, msg):
        self.data.append({'sender': sender, 'msg': msg})

#top of page errors
class ErrorStatus(BoxLayout):
    rgba = ListProperty([0.5, 0.5, 0.5, 1])

    def __init__(self, **kwargs):
        super(ErrorStatus, self).__init__(**kwargs)

    def setStatus(self, isError):
        self.rgba = [1, 0, 0, 1] if isError else [0.5, 0.5, 0.5, 1] 

#total message
class LabelContainer(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelContainer, self).__init__(**kwargs)

#message text
class AlignedLabel(Label):
    def __init__(self, **kwargs):
        super(AlignedLabel, self).__init__(**kwargs)

#main app container
class MainScreen(BoxLayout):
        def addMessage(self):
            textbox = App.get_running_app().root.children[0].children[0].children[1]
            message = textbox.text

            #dispatch to queue
            #message will be hydrated with clock by the broadcast handler
            partiallyCompleteMessage = messageToJson(constructMessage(MessageType.BROADCAST_MESSAGE, {}, message, None))
            App.get_running_app().dispatchToQueue(partiallyCompleteMessage)

            #update UI
            textbox.text = ''
            App.get_running_app().root.children[0].children[1].children[0].addMessage('You', message)


#main GUI class, handles display and contains control methods 
class GUI(App):
           
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_request_close=self.cleanup)
    
    def cleanup(self, *args):
        App.stop(self)
        Window.close()

    def setQueue(self, queue):
        self.queue = queue

    def dispatchToQueue(self, message):
        self.queue.put(message)

    def clearStatusMessage(self):
        App.get_running_app().root.children[0].children[2].children[0].text = ''
        App.get_running_app().root.children[0].children[2].clearStatus()

    def setStatusMessage(self, status, isError):
        App.get_running_app().root.children[0].children[2].children[0].text = status
        App.get_running_app().root.children[0].children[2].setStatus(isError)

    def setPeerCount(self, peerCount):
        App.get_running_app().root.children[0].children[2].children[1].children[0].text = 'Remaining Peers: {0}'.format(peerCount)

    def build(self):
        return MainScreen()


#************************************************************
#UI update methods, schedule events for the GUI thread to perform

#TODO CHANGE SO WE SEND AN ENTIRE NEW LIST, RATHER THAN APPENDING
#OTHERWISE SCHEDULING DIFFERENCES COULD LEAD TO THE APPEARANCE OF NON-CAUSAL UPDATES
def textUpdateGUI(sender, message):
    Clock.schedule_once(lambda dt: App.get_running_app().root.children[0].children[1].children[0].addMessage(sender, message), 0.001)

def statusUpdateGUI(status, isError):
    Clock.schedule_once(lambda dt: App.get_running_app().setStatusMessage(status, isError), 0.001)

def updateLivePeerCountGUI(newCount):
    Clock.schedule_once(lambda dt: App.get_running_app().setPeerCount(newCount), 0.001)