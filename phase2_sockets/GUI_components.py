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

class Messages(RecycleView):
    def __init__(self, **kwargs):
        super(Messages, self).__init__(**kwargs)
        self.data = []

    def addMessage(self, sender, msg):
        self.data.append({'sender': sender, 'msg': msg})

class ErrorStatus(BoxLayout):
    rgba = ListProperty([0.5, 0.5, 0.5, 1])

    def __init__(self, **kwargs):
        super(ErrorStatus, self).__init__(**kwargs)

    def clearStatus(self):
        self.rgba = [0.5, 0.5, 0.5, 1]

    def setStatus(self, isError):
        self.rgba = [1, 0, 0, 1] if isError else [0, 1, 0, 1] 

class LabelContainer(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelContainer, self).__init__(**kwargs)

class AlignedLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class MainScreen(BoxLayout):
        def addMessage(self):
            textbox = App.get_running_app().root.children[0].children[0].children[1]
            message = textbox.text

            #dispatch to queue
            App.get_running_app().dispatchToQueue(message)

            #update UI
            textbox.text = ''
            App.get_running_app().root.children[0].children[1].children[0].addMessage('You', message)

class GUI(App):
           
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        print(args)
        Window.bind(on_request_close=self.cleanup)
        self.queue = None
    
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

    def build(self):
        return MainScreen()

#TODO CHANGE SO WE SEND AN ENTIRE NEW LIST, RATHER THAN APPENDING
#OTHERWISE SCHEDULING DIFFERENCES COULD LEAD TO THE APPEARANCE OF NON-CAUSAL UPDATES
def textUpdateGUI(sender, message):
    Clock.schedule_once(lambda dt: App.get_running_app().root.children[0].children[1].children[0].addMessage(sender, message), 0.001)

def statusUpdateGUI(status, isError):
    Clock.schedule_once(lambda dt: App.get_running_app().setStatusMessage(status, isError), 0.001)

def clearStatusGUI():
    Clock.schedule_once(lambda dt: App.get_running_app().clearStatusMessage(), 0.001)