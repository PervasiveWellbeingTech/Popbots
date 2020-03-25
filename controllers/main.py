import re
import random
import time
import sys
import traceback

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from exceptions.badinput import BadKeywordInputError
from exceptions.nopossibleanswer import NoPossibleAnswer
from exceptions.authoringerror import AuthoringError

from controllers.message import get_bot_response

from models.user import HumanUser,Users
from models.utils import get_user_id_from_name
from models.core.config import config_string
from models.conversation import Conversation,Message,Content,ContentFinders

from utils import log


engine = create_engine(config_string())
Session = sessionmaker(bind=engine)
session = Session()


def database_push(element):
    session.add(element)
    session.commit()
    return element.id
def push_message(text,user_id,index,receiver_id,sender_id,conversation_id,stressor):
    content_user = Content(text=text,user_id=user_id)
    content_id_user  = database_push(content_user)
    message_user = Message(index=index,receiver_id=receiver_id,sender_id=sender_id,content_id=content_id_user,conversation_id = conversation_id,stressor=stressor,datetime=datetime.now())
    _ = database_push(message_user) 

def get_bot_ids(exclude):
    return [x.id for x in session.query(Users).filter_by(category_id=2) if (x.name not in {'Onboarding Bot'} and x.id not in {exclude})]
def image_fetcher(bot_text):
    
    start = bot_text.find("$img$") + len("$img$")
    end = bot_text.find("$img$",start)
    substring = bot_text[start:end]
    
    bot_text = bot_text.replace("$img$"+substring+"$img$","")

    img = open('./img/{}.png'.format(substring), 'rb')
    
    return bot_text,img



def response_engine(user_id,user_message):

    log('DEBUG',f"Incoming message is: "+str(user_message))
    #Set custom keyboard (defaults to none)
    reply_markup = {'type':'normal','resize_keyboard':True,'text':""}
    response_dict={'response_list':None,'img':None,'command':None,'reply_markup':reply_markup}

    initialized = False
    next_index = None
    bot_id = None
    
    conversation = session.query(Conversation).filter_by(user_id=user_id,closed = False).order_by(Conversation.datetime.desc()).first()
    
    if conversation:
        log('INFO',f"Conversation detected with the id {conversation.id}") 

        conversation_id = conversation.id
        if (datetime.now() - conversation.datetime).seconds > 3600 : #Time out
            conversation.closed = True
            conversation_id = None
            session.commit()
    else: 
        conversation_id = None
        print(f"Warning the conversation id is none and the message is {user_message}") 

    print(f"This is conversational id {conversation_id}")

    ############        Special Cases        ############
    user = session.query(HumanUser).filter_by(user_id=user_id).first()
    
    if user is not None:
        log('DEBUG',f'User is known as: {user.name}')
    else:
        log('DEBUG',f"User is None, with class {user}")
        user_message = 'start' #temporary fix
        
    
    
    if 'start' in user_message: #restart

        log('INFO','Started a new session via /start')
        if user is None:
            user = HumanUser(user_id=user_id)
            user.subject_id = re.findall(' ([0-9]+)', user_message)
            user.language_id = 1 # for englishe
            user.language_type_id = 1 # for formal 
            user.category_id = 1
            
            user.name = "Human" # this is the default
            session.add(user)
            session.commit()

        if conversation: # closing the previous conversation is there is
            conversation.closed = True
            session.commit()

        dt = datetime.now()
        conversation = Conversation(user_id=user_id,datetime=dt,closed=False)
        conversation_id = database_push(conversation)

       
        bot_id = get_user_id_from_name("Onboarding Bot") # this is the onboarding bot, serve multiple purposes
        next_index = 0 

    
    elif re.match(r'Hi',user_message):

        if conversation: # closing the previous conversation
            conversation.closed = True
            session.commit()
        
        initialized = True
        dt = datetime.now()
        conversation = Conversation(user_id=user_id,datetime=dt,closed=False)
        conversation_id = database_push(conversation)
        bot_id = get_user_id_from_name("Onboarding Bot")

    if conversation is None:
        print("[WARNING] There is no active conversation and the user did not type 'start' or 'Hi' force creating a new one ")
        dt = datetime.now()
        conversation = Conversation(user_id=user_id,datetime=dt,closed=False)
        conversation_id = database_push(conversation)
        message = None
    else:
        message = session.query(Message).filter_by(receiver_id=user_id,conversation_id=conversation_id).order_by(Message.id.desc()).first() # finding the lastest message
    
    if message and initialized == False and next_index is None:
        next_index = message.index 
        bot_id = message.sender_id
        print(f"[INFO] Found a previous message pointing to {next_index} and was send by bot_id {bot_id}")

    elif initialized and next_index is None: # in this case it is normal to have no message
        print("[WARNING] Entered in the in initized Here")
        bot_id = get_user_id_from_name("Onboarding Bot") # this is where it will need to be smart
        next_index = 14
        print(f"[INFO] Initialized with next_index =  {next_index} and was send to bot_id {bot_id}")
    elif message is None and next_index is None: # there is no message 
        print("[WARNING] Should not have entered in the no message, no in itialized scenario but did")
        next_index=0
        possible_bot = get_bot_ids(bot_id)
        bot_id =  possible_bot[random.randint(0,len(possible_bot)-1)]

    if next_index != 0 and next_index is not None:

        content_index = session.query(ContentFinders).filter_by(user_id=bot_id,message_index = next_index).first().id
        print(f"[INFO] Finding selector for message_index =  {next_index} and was send by bot_id {bot_id}")
    else:
        content_index = session.query(ContentFinders).filter_by(user_id=bot_id,message_index = 0).first().id


    
    if re.match(r'/switch', user_message): #switch
        
        next_index=0
        possible_bot = get_bot_ids(bot_id)
        bot_id =  possible_bot[random.randint(0,len(possible_bot)-1)]
        content_index = session.query(ContentFinders).filter_by(user_id=bot_id,message_index = 0).first().id



    problem = "that"

    bot_response_time = time.time()
    bot_text,next_index,keyboard,triggers = get_bot_response(bot_id=bot_id,next_index=next_index,user_response=user_message,content_index=content_index)
    log('INFO',f'Bot response engine took {"% 12.2f" % (time.time()-bot_response_time)} seconds')
    if str(keyboard)=="default":
        reply_markup = {'type':'default','resize_keyboard':True,'text':""}
    else:
        reply_markup = {'type':'inlineButton','resize_keyboard':True,'text':str(keyboard)}
        

    try:

        if len(triggers)>0:
            for trigger in triggers:
                if "#" in trigger:
                    trigger = trigger.replace("#","")
                    if len(trigger.split(".")) ==2:
                        class_name,class_variable = trigger.split(".")
                        #exec(trigger+"="+str(user_message) )
                        setattr(locals()[class_name],class_variable,user_message)
                    else: # we assume that it is one
                    
                        locals()[trigger]=user_message


    except Exception as error:
        log('ERROR',error)

    if "$img$" in bot_text:
        bot_text,img = image_fetcher(bot_text)
        response_dict['img'] = img
        

    log('DEBUG',f'Bot text would be: {bot_text}')

    if "<SWITCH>" in bot_text:
        response_dict['command'] = "skip"
        next_index = 0
        possible_bot = get_bot_ids(bot_id)
        bot_id =  possible_bot[random.randint(0,len(possible_bot)-1)]

        log("DEBUG",f" Switching to a new bot with bot_id = {bot_id} ")
    
    if bot_text == "" or bot_text is None:
        log("ERROR" ,f"bot_text was empty or None, forcing jump to a new bot")
        next_index = 0
        possible_bot = get_bot_ids(bot_id)
        bot_id =  possible_bot[random.randint(0,len(possible_bot)-1)]
        


    log("DEBUG",f"The user id is: {user_id}")

    if next_index is None:
        log('ERROR',"Something went wrong next_index is None ???? Will log bad data")

    push_message(text=user_message,user_id=user_id,index=None,receiver_id=bot_id,sender_id=user_id,conversation_id=conversation_id,stressor=problem) # pushing user message
    push_message(text=bot_text,user_id=bot_id,index=next_index,receiver_id=user_id,sender_id=bot_id,conversation_id=conversation_id,stressor=problem) # pushing the bot response

   

    bot_user = session.query(Users).filter_by(id = bot_id).first()
    response_dict['response_list'] = bot_text.strip().replace("'","\\'").split("\\n")

    try: # formatting the text with the neccessary info eg: user:name, etc...
        templist = []
        for res in response_dict['response_list']:
            templist.append(eval(f"f'{res}'"))
        response_dict['response_list'] = templist
        
    except BaseException as error:
        log('ERROR',f"String interpolation for {bot_user.id},{bot_user.name} failed due to: {error}")
    
    if "<CONVERSATION_END>" in bot_text:
        print('Entered in the conversation end')
        
        conversation.closed = True
        session.commit()
        response_dict['command'] = "skip"

    if bot_text == "<START>":
        response_dict['command'] = "skip"


    response_dict['reply_markup'] = reply_markup
    response_dict['bot_name'] = bot_user.name
    log('DEBUG','------------------------END OF MESSAGE ENGINE------------------------')

    return response_dict

def dialog_flow_engine(user_id,user_message):

    reply_markup = {'type':'inlineButton','resize_keyboard':True,'text':"Hi"}
    try:
        command = "skip"
        while command == "skip":

            response_engine_time = time.time()
            response_dict  = response_engine(user_id,user_message)
            log('INFO',f'Response engine took {time.time()-response_engine_time} to answer' )
            command = response_dict['command']
                
        return response_dict
    
    except BadKeywordInputError as error:
        log('ERROR',error)
        response_dict={'response_list':["Oops, sorry for being not precise enought...","I expected: '"+ "' or '".join(set(error.features))+"' as an answer for the latest question","Can you answer again please?"],'img':None,'command':None,'reply_markup':reply_markup,'bot_name':"Onboarding Bot"}
        return response_dict
    except AuthoringError as error:

        log('ERROR',":x: [FATAL AUTHORING ERROR] "+str(error))

        response_dict={'response_list':["My creators lest me short of answer for this one","I'll probably go to sleep until they fix my issue",'Sorry for that, say "Hi" to start a new conversation'],'img':None,'command':None,'reply_markup':reply_markup,'bot_name':"Onboarding Bot"}
        return response_dict

    except NoPossibleAnswer as error:
        reply_markup = {'type':'inlineButton','resize_keyboard':True,'text':"Hi"}
        log('ERROR',":loudspeaker: [FATAL ERROR]" +str(error))
        return {'response_list':['It seems that my bot brain lost itself in the flow...','Sorry for that, say "Hi" to start a new conversation'],'img':None,'command':None,'reply_markup':reply_markup,'bot_name':"Onboarding Bot"}

    except BaseException as error:
        reply_markup = {'type':'inlineButton','resize_keyboard':True,'text':"Hi"}
        response_dict={'response_list':['It seems that my bot brain lost itself in the flow...','Sorry for that, say "Hi" to start a new conversation'],'img':None,'command':None,'reply_markup':reply_markup,'bot_name':"Onboarding Bot"}
        

        tb = traceback.TracebackException.from_exception(error)
        log('ERROR',":loudspeaker: [FATAL ERROR]" + str(error)+str(''.join(tb.stack.format())))
        print(str(''.join(tb.stack.format())))
        session.rollback()
        return response_dict
        
    

if __name__ == "__main__":

    bot_response = ""
    while bot_response != "<CONVERSATION_END>":
        user_response = input("My  input: ")
        bot_response = dialog_flow_engine(user_id=1234567,user_message=user_response)
        print("Bot reply: " + str(bot_response['response_list']))

